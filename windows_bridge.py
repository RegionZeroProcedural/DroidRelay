#!/usr/bin/env python3
"""
Windows side SOCKS5 bridge.

Exposes:
    SOCKS5 127.0.0.1:1080

For TCP CONNECT:
    SOCKS -> ADB-forwarded Android relay -> Internet

For UDP ASSOCIATE:
    SOCKS UDP packet -> framed TCP over ADB -> Android UDP socket -> Internet

This keeps all PC<->phone transport inside ADB TCP while still supporting
SOCKS5 UDP clients such as tun2socks.
"""

import socket
import struct
import threading
import select
import time

SOCKS_HOST = "127.0.0.1"
SOCKS_PORT = 1080

ANDROID_RELAY_HOST = "127.0.0.1"
ANDROID_RELAY_PORT = 19090

BUFFER_SIZE = 65536
MAX_FRAME = 1024 * 1024

CMD_TCP = 0x01
CMD_UDP = 0x03
STATUS_OK = 0x00


def recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("connection closed")
        data.extend(chunk)
    return bytes(data)


def send_frame(sock, payload):
    if len(payload) > MAX_FRAME:
        raise ValueError("frame too large")
    sock.sendall(struct.pack("!I", len(payload)) + payload)


def recv_frame(sock):
    size = struct.unpack("!I", recv_exact(sock, 4))[0]
    if size > MAX_FRAME:
        raise ValueError(f"frame too large: {size}")
    return recv_exact(sock, size)


def encode_address(host, port):
    try:
        return b"\x01" + socket.inet_pton(socket.AF_INET, host) + struct.pack("!H", port)
    except OSError:
        pass

    try:
        return b"\x04" + socket.inet_pton(socket.AF_INET6, host) + struct.pack("!H", port)
    except OSError:
        pass

    raw = host.encode("idna")
    if len(raw) > 255:
        raise ValueError("hostname too long")
    return b"\x03" + bytes([len(raw)]) + raw + struct.pack("!H", port)


def decode_address_from_socket(sock):
    atyp = recv_exact(sock, 1)[0]

    if atyp == 0x01:
        host = socket.inet_ntop(socket.AF_INET, recv_exact(sock, 4))
    elif atyp == 0x03:
        n = recv_exact(sock, 1)[0]
        host = recv_exact(sock, n).decode("idna")
    elif atyp == 0x04:
        host = socket.inet_ntop(socket.AF_INET6, recv_exact(sock, 16))
    else:
        raise ValueError("unsupported address type")

    port = struct.unpack("!H", recv_exact(sock, 2))[0]
    return host, port


def decode_address_from_bytes(buf, offset=0):
    if offset >= len(buf):
        raise ValueError("missing address type")

    atyp = buf[offset]
    offset += 1

    if atyp == 0x01:
        host = socket.inet_ntop(socket.AF_INET, buf[offset:offset + 4])
        offset += 4
    elif atyp == 0x03:
        n = buf[offset]
        offset += 1
        host = buf[offset:offset + n].decode("idna")
        offset += n
    elif atyp == 0x04:
        host = socket.inet_ntop(socket.AF_INET6, buf[offset:offset + 16])
        offset += 16
    else:
        raise ValueError("unsupported address type")

    port = struct.unpack("!H", buf[offset:offset + 2])[0]
    offset += 2
    return host, port, offset


def socks_reply(conn, rep, host="0.0.0.0", port=0):
    conn.sendall(b"\x05" + bytes([rep]) + b"\x00" + encode_address(host, port))


def socks_handshake(conn):
    ver, nmethods = recv_exact(conn, 2)
    if ver != 5:
        raise ValueError("not SOCKS5")

    methods = recv_exact(conn, nmethods)
    if 0x00 not in methods:
        conn.sendall(b"\x05\xff")
        raise ValueError("client does not support no-auth")

    conn.sendall(b"\x05\x00")

    ver, cmd, rsv, atyp = recv_exact(conn, 4)
    if ver != 5:
        raise ValueError("invalid SOCKS version")

    # We already consumed ATYP, so decode the rest manually by rebuilding it.
    if atyp == 0x01:
        host = socket.inet_ntop(socket.AF_INET, recv_exact(conn, 4))
    elif atyp == 0x03:
        n = recv_exact(conn, 1)[0]
        host = recv_exact(conn, n).decode("idna")
    elif atyp == 0x04:
        host = socket.inet_ntop(socket.AF_INET6, recv_exact(conn, 16))
    else:
        socks_reply(conn, 0x08)
        raise ValueError("unsupported address type")

    port = struct.unpack("!H", recv_exact(conn, 2))[0]
    return cmd, host, port


def bidirectional_tcp(a, b):
    """Lossless, backpressure-aware, full-duplex TCP relay.

    Both sockets are nonblocking. Never use sendall() on a nonblocking
    socket: a temporarily full send buffer must be retried after the socket
    becomes writable, not mistaken for a disconnected peer.
    """
    peers = {a: b, b: a}
    pending = {a: bytearray(), b: bytearray()}
    read_open = {a: True, b: True}
    write_shutdown = {a: False, b: False}
    max_pending = 512 * 1024

    a.setblocking(False)
    b.setblocking(False)

    while True:
        readers = [s for s in (a, b)
                   if read_open[s] and len(pending[peers[s]]) < max_pending]
        writers = [s for s in (a, b) if pending[s]]

        if not readers and not writers:
            return

        readable, writable, exceptional = select.select(
            readers, writers, [a, b], 30.0
        )
        if exceptional:
            raise ConnectionError("exceptional TCP socket condition")

        # Read from each side and queue bytes for the other side.
        for src in readable:
            try:
                data = src.recv(BUFFER_SIZE)
            except (BlockingIOError, InterruptedError):
                continue
            if data:
                pending[peers[src]].extend(data)
            else:
                read_open[src] = False

        # Only write when the socket is writable. Preserve unsent bytes.
        for dst in writable:
            if not pending[dst]:
                continue
            try:
                n = dst.send(pending[dst])
            except (BlockingIOError, InterruptedError):
                continue
            if n == 0:
                raise ConnectionError("TCP send returned zero bytes")
            del pending[dst][:n]

        # Propagate a clean EOF after forwarding all already-received data.
        # Keep the other direction open to allow a full HTTP response.
        for src in (a, b):
            dst = peers[src]
            if not read_open[src] and not pending[dst] and not write_shutdown[dst]:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                write_shutdown[dst] = True


def open_android_relay():
    s = socket.create_connection((ANDROID_RELAY_HOST, ANDROID_RELAY_PORT), timeout=10)
    s.settimeout(None)
    return s


def handle_connect(client, host, port):
    tunnel = None
    socks_success_sent = False
    try:
        tunnel = open_android_relay()
        tunnel.sendall(bytes([CMD_TCP]) + encode_address(host, port))

        status = recv_exact(tunnel, 1)[0]
        if status != STATUS_OK:
            socks_reply(client, 0x05)
            return

        socks_reply(client, 0x00, "127.0.0.1", 0)
        socks_success_sent = True
        print(f"[TCP] {host}:{port}")
        bidirectional_tcp(client, tunnel)
    except Exception as e:
        # Never inject a SOCKS error into an already-established TLS stream.
        if not socks_success_sent:
            try:
                socks_reply(client, 0x01)
            except Exception:
                pass
        print(f"[TCP ERROR] {host}:{port} - {e}")
    finally:
        if tunnel is not None:
            try:
                tunnel.close()
            except Exception:
                pass


def parse_socks_udp_packet(packet):
    # RFC 1928 UDP request:
    # RSV(2) FRAG(1) ATYP(1) DST.ADDR DST.PORT DATA
    if len(packet) < 4 or packet[0:2] != b"\x00\x00":
        raise ValueError("invalid SOCKS UDP packet")

    frag = packet[2]
    if frag != 0:
        raise ValueError("SOCKS UDP fragmentation is not supported")

    host, port, pos = decode_address_from_bytes(packet, 3)
    return host, port, packet[pos:]


def build_socks_udp_packet(host, port, payload):
    return b"\x00\x00\x00" + encode_address(host, port) + payload


def udp_tunnel_reader(tunnel, udp_sock, client_addr_ref, stop):
    try:
        while not stop.is_set():
            frame = recv_frame(tunnel)
            host, port, pos = decode_address_from_bytes(frame, 0)
            payload = frame[pos:]

            client_addr = client_addr_ref[0]
            if client_addr is not None:
                udp_sock.sendto(build_socks_udp_packet(host, port, payload), client_addr)
    except Exception:
        stop.set()


def handle_udp_associate(client):
    udp_sock = None
    tunnel = None
    stop = threading.Event()
    client_addr_ref = [None]

    try:
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(("127.0.0.1", 0))
        udp_sock.settimeout(1.0)

        bind_host, bind_port = udp_sock.getsockname()

        tunnel = open_android_relay()
        tunnel.sendall(bytes([CMD_UDP]))
        status = recv_exact(tunnel, 1)[0]

        if status != STATUS_OK:
            socks_reply(client, 0x01)
            return

        socks_reply(client, 0x00, bind_host, bind_port)
        print(f"[UDP] local relay 127.0.0.1:{bind_port}")

        reader = threading.Thread(
            target=udp_tunnel_reader,
            args=(tunnel, udp_sock, client_addr_ref, stop),
            daemon=True,
        )
        reader.start()

        client.setblocking(False)

        while not stop.is_set():
            # Per SOCKS5, the UDP association lives while the TCP control
            # connection stays open.
            try:
                readable, _, _ = select.select([client], [], [], 0)
                if client in readable:
                    data = client.recv(1)
                    if not data:
                        break
            except (BlockingIOError, InterruptedError):
                pass
            except OSError:
                break

            try:
                packet, sender = udp_sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break

            # Lock the association to the first local UDP sender.
            if client_addr_ref[0] is None:
                client_addr_ref[0] = sender
            elif sender != client_addr_ref[0]:
                continue

            try:
                host, port, payload = parse_socks_udp_packet(packet)
                send_frame(tunnel, encode_address(host, port) + payload)
            except Exception as e:
                # Bad datagram: ignore it rather than kill the association.
                print(f"[UDP PACKET ERROR] {e}")

    except Exception as e:
        try:
            socks_reply(client, 0x01)
        except Exception:
            pass
        print(f"[UDP ERROR] {e}")
    finally:
        stop.set()
        for s in (udp_sock, tunnel):
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        print("[UDP] association closed")


def handle_client(client, address):
    try:
        cmd, host, port = socks_handshake(client)

        if cmd == 0x01:       # CONNECT
            handle_connect(client, host, port)
        elif cmd == 0x03:     # UDP ASSOCIATE
            handle_udp_associate(client)
        else:
            socks_reply(client, 0x07)
    except Exception as e:
        print(f"[SOCKS ERROR] {address}: {e}")
    finally:
        try:
            client.close()
        except Exception:
            pass


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((SOCKS_HOST, SOCKS_PORT))
    server.listen(128)

    print("=" * 52)
    print(" Windows USB Gateway Bridge")
    print("=" * 52)
    print(f" SOCKS5: {SOCKS_HOST}:{SOCKS_PORT}")
    print(f" Android relay via ADB: {ANDROID_RELAY_HOST}:{ANDROID_RELAY_PORT}")
    print(" Supports SOCKS5 TCP CONNECT + UDP ASSOCIATE.")
    print("=" * 52)

    try:
        while True:
            client, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(client, addr),
                daemon=True,
            ).start()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        server.close()


if __name__ == "__main__":
    main()
