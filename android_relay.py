#!/usr/bin/env python3
"""
Android / Pydroid side of the USB Internet gateway.

Listens only on 127.0.0.1:19090. Windows reaches it through:
    adb forward tcp:19090 tcp:19090

Protocol:
  0x01 + SOCKS-style encoded destination -> TCP CONNECT tunnel
  0x03                               -> UDP-over-TCP association

No third-party Python packages are required.
"""

import socket
import struct
import threading
import select
import time

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 19090
TCP_CONNECT_TIMEOUT = 15
BUFFER_SIZE = 65536
MAX_FRAME = 1024 * 1024
UDP_SOCKET_TIMEOUT = 1.0

CMD_TCP = 0x01
CMD_UDP = 0x03

STATUS_OK = 0x00
STATUS_FAIL = 0x01


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
        packed = socket.inet_pton(socket.AF_INET, host)
        return b"\x01" + packed + struct.pack("!H", port)
    except OSError:
        pass

    try:
        packed = socket.inet_pton(socket.AF_INET6, host)
        return b"\x04" + packed + struct.pack("!H", port)
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
        if offset + 4 > len(buf):
            raise ValueError("truncated IPv4 address")
        host = socket.inet_ntop(socket.AF_INET, buf[offset:offset + 4])
        offset += 4
    elif atyp == 0x03:
        if offset >= len(buf):
            raise ValueError("truncated domain length")
        n = buf[offset]
        offset += 1
        if offset + n > len(buf):
            raise ValueError("truncated domain")
        host = buf[offset:offset + n].decode("idna")
        offset += n
    elif atyp == 0x04:
        if offset + 16 > len(buf):
            raise ValueError("truncated IPv6 address")
        host = socket.inet_ntop(socket.AF_INET6, buf[offset:offset + 16])
        offset += 16
    else:
        raise ValueError("unsupported address type")

    if offset + 2 > len(buf):
        raise ValueError("truncated port")
    port = struct.unpack("!H", buf[offset:offset + 2])[0]
    offset += 2
    return host, port, offset


def resolve_udp_target(host, port):
    infos = socket.getaddrinfo(host, port, 0, socket.SOCK_DGRAM)
    if not infos:
        raise OSError("could not resolve UDP target")
    family, _, _, _, sockaddr = infos[0]
    return family, sockaddr


def bidirectional_tcp(a, b):
    a.setblocking(False)
    b.setblocking(False)
    sockets = [a, b]

    while True:
        try:
            readable, _, exceptional = select.select(sockets, [], sockets, 30.0)
        except (OSError, ValueError):
            return

        if exceptional:
            return
        if not readable:
            continue

        for src in readable:
            dst = b if src is a else a
            try:
                data = src.recv(BUFFER_SIZE)
            except (BlockingIOError, InterruptedError):
                continue
            except OSError:
                return

            if not data:
                return

            try:
                dst.sendall(data)
            except OSError:
                return


def handle_tcp(conn):
    remote = None
    try:
        host, port = decode_address_from_socket(conn)
        print(f"[TCP] {host}:{port}")

        remote = socket.create_connection((host, port), timeout=TCP_CONNECT_TIMEOUT)
        conn.sendall(bytes([STATUS_OK]))
        bidirectional_tcp(conn, remote)

    except Exception as e:
        try:
            conn.sendall(bytes([STATUS_FAIL]))
        except Exception:
            pass
        print(f"[TCP ERROR] {e}")
    finally:
        if remote is not None:
            try:
                remote.close()
            except Exception:
                pass


def udp_sender_loop(conn, udp4, udp6, stop):
    """Read framed UDP datagrams from Windows and emit them to the Internet."""
    try:
        while not stop.is_set():
            frame = recv_frame(conn)
            host, port, pos = decode_address_from_bytes(frame, 0)
            payload = frame[pos:]

            family, sockaddr = resolve_udp_target(host, port)
            s = udp6 if family == socket.AF_INET6 else udp4
            if s is None:
                continue
            s.sendto(payload, sockaddr)
    except Exception:
        stop.set()


def handle_udp(conn):
    udp4 = None
    udp6 = None
    stop = threading.Event()

    try:
        udp4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp4.bind(("0.0.0.0", 0))
        udp4.setblocking(False)

        try:
            udp6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            udp6.bind(("::", 0))
            udp6.setblocking(False)
        except OSError:
            udp6 = None

        conn.sendall(bytes([STATUS_OK]))
        print("[UDP] association opened")

        tx = threading.Thread(
            target=udp_sender_loop,
            args=(conn, udp4, udp6, stop),
            daemon=True,
        )
        tx.start()

        sockets = [udp4] + ([udp6] if udp6 is not None else [])

        while not stop.is_set():
            try:
                readable, _, _ = select.select(sockets, [], [], 1.0)
            except (OSError, ValueError):
                break

            for s in readable:
                try:
                    data, addr = s.recvfrom(65535)
                except OSError:
                    continue

                host = addr[0]
                port = addr[1]
                send_frame(conn, encode_address(host, port) + data)

    except Exception as e:
        try:
            conn.sendall(bytes([STATUS_FAIL]))
        except Exception:
            pass
        print(f"[UDP ERROR] {e}")
    finally:
        stop.set()
        for s in (udp4, udp6):
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        print("[UDP] association closed")


def handle_client(conn, addr):
    try:
        cmd = recv_exact(conn, 1)[0]
        if cmd == CMD_TCP:
            handle_tcp(conn)
        elif cmd == CMD_UDP:
            handle_udp(conn)
        else:
            conn.sendall(bytes([STATUS_FAIL]))
    except Exception as e:
        print(f"[CLIENT ERROR] {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(128)

    print("=" * 52)
    print(" Android/Pydroid USB Internet Relay")
    print("=" * 52)
    print(f" Listening on {LISTEN_HOST}:{LISTEN_PORT}")
    print(" Keep Pydroid running and keep Wi-Fi OFF if you")
    print(" want the phone's cellular connection specifically.")
    print("=" * 52)

    try:
        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True,
            ).start()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        server.close()


if __name__ == "__main__":
    main()
