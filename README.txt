# Phone USB Internet Gateway - DroidRelay

### Android-to-Windows USB Internet Sharing via ADB & SOCKS5

Share your Android phone's internet connection with a Windows PC through USB debugging, without enabling Android's native USB tethering or mobile hotspot functionality.

This project creates a custom SOCKS5 networking tunnel over Android Debug Bridge (ADB), allowing Windows applications to access the internet through your Android device.

**No hotspot required. No native tethering required. Just USB debugging.**

## Key Features

* **No native tethering required** — Uses ADB instead of Android's built-in tethering functionality.
* **Hotspot throttling avoidance** — Tested to avoid hotspot-specific throttling and usage tracking under the developer's network conditions.
* **SOCKS5 networking** — Custom Python-based internet relay.
* **TCP and UDP support** — Relays TCP connections and encapsulates UDP traffic for transmission over USB.
* **System-wide connectivity** — Uses tun2socks and Wintun to route Windows network traffic.
* **Automated dependency installation** — Includes Windows and Termux setup scripts.
* **Simple connection management** — Start and stop the internet gateway using Windows batch files.
* **Local-only proxy** — SOCKS5 services bind to loopback interfaces instead of exposing an open proxy to the network.

---

## How It Works

Instead of activating Android's native tethering interface, this project establishes a custom networking pathway.

```text
            WINDOWS PC
                |
        Windows Applications
                |
             tun2socks
                |
        SOCKS5 Proxy Server
          127.0.0.1:1080
                |
         windows_bridge.py
                |
         ADB TCP Forwarding
          127.0.0.1:19090
                |
          USB DEBUGGING
                |
         android_relay.py
                |
       Android Network Stack
                |
       Mobile Data Connection
                |
             INTERNET
```

### TCP Traffic

TCP connections are forwarded through the SOCKS5 proxy and carried through the ADB connection to the Android relay.

The Android device establishes the outgoing connection using its own internet access.

### UDP Traffic

UDP traffic requires additional processing because the ADB forwarding connection uses TCP.

The relay implements UDP encapsulation:

```text
Windows UDP Traffic
        |
      SOCKS5
        |
  UDP Packet Framing
        |
    TCP Transport
        |
   ADB USB Tunnel
        |
   Android Relay
        |
   UDP Transmission
        |
      Internet
```

UDP packets are encapsulated into framed TCP messages for the Windows-to-Android transport.

Once received by Android, the relay transmits them as real UDP packets.

**Note:** UDP-over-TCP introduces additional latency and head-of-line blocking. Latency-sensitive applications, particularly online games, may perform differently from native USB tethering.

---

# Requirements

## Android

* Android smartphone
* USB debugging enabled
* Developer Options enabled
* Active cellular data or Wi-Fi connection
* Termux with Python 3, or Pydroid 3
* USB cable supporting data transfer

## Windows

* Windows 10 or Windows 11
* Python 3
* Android Debug Bridge (ADB)
* tun2socks
* Wintun
* Administrator privileges for network configuration

---

# Quick Start

Already installed everything?

You only need two steps to reconnect.

### 1. Android — Termux

```bash
cd "/path/to/your/folder"
python android_relay.py
```

### 2. Windows — Administrator PowerShell

```powershell
cd "C:\path\to\your\folder"
.\start_full_tunnel.bat
```

**Your Android internet connection is now available through the configured Windows tunnel.**

To disconnect:

```powershell
.\stop_full_tunnel.bat
```

---

**Dependency installation scripts are included to simplify the setup process.**

---

# Installation

## Step 1: Download the Project

Download or clone this repository onto your Windows computer.

```powershell
git clone "https://github.com/RegionZeroProcedural/DroidRelay"
```

Navigate into the downloaded project directory.

```powershell
cd DroidRelay
```

You will also need the Android relay and its setup script on your Android device.

You can transfer the required files using USB, Git, or another file transfer method.

---

## Step 2: Set Up Android

### Enable USB Debugging

1. Open Android **Settings**.
2. Navigate to **About Phone**.
3. Tap **Build Number** seven times to enable Developer Options.
4. Return to Settings and open **Developer Options**.
5. Enable **USB Debugging**.
6. Connect your phone to your Windows computer using USB.
7. Accept the USB debugging authorization prompt on your phone.

**IMPORTANT: Do not enable USB tethering.**

The relay communicates through USB debugging instead of Android's native tethering functionality.

If you specifically want to use cellular data, disable Wi-Fi on your Android device.

### Install Dependencies with Termux

Install and open Termux.

Navigate to the directory containing the project files:

```bash
cd "/path/to/your/folder"
```

Run the included dependency installer:

```bash
bash setup_termux.sh
```

This script handles the Android-side dependency setup.

Once installation completes, you can launch the relay:

```bash
python android_relay.py
```

Keep the Termux session running while sharing your internet connection.

**Alternative: Pydroid 3**

You can also run `android_relay.py` using Pydroid 3.

The Termux installer is intended for Termux; Pydroid users must ensure the Python dependencies are available in their Pydroid environment.

---

## Step 3: Install Windows Dependencies

Open the project folder on your Windows computer.

Locate:

```text
setup_windows.bat
```

**Run the setup script as Administrator.**

Alternatively, open PowerShell as Administrator, navigate to the project directory, and execute:

```powershell
.\setup_windows.bat
```

This script performs the Windows-side dependency setup.

Follow any instructions displayed by the installer.

Once the setup completes, verify that the required networking components are available.

The project uses:

* Python 3
* ADB
* tun2socks
* Wintun

**Note:** If the installer reports missing prerequisites or installation errors, resolve those issues before proceeding.

---

# First Connection Test

Before enabling system-wide networking, verify that the basic SOCKS5 relay works correctly.

## Step 1: Start the Android Relay

On your Android device, open Termux.

Navigate to your project directory:

```bash
cd "/path/to/your/folder"
```

Start the relay:

```bash
python android_relay.py
```

Leave it running.

## Step 2: Verify USB Debugging

On Windows, open PowerShell or Command Prompt.

Run:

```powershell
adb devices
```

Your Android device should appear in the list of connected devices.

If it displays:

```text
unauthorized
```

Unlock your phone and accept the USB debugging authorization prompt.

## Step 3: Create the ADB Forward

Run:

```powershell
adb forward tcp:19090 tcp:19090
```

This forwards Windows TCP port `19090` to the Android relay.

## Step 4: Start the Windows Bridge

From the Windows project directory, run:

```powershell
python windows_bridge.py
```

This launches the Windows-side SOCKS5 bridge.

The proxy is available at:

```text
SOCKS5 Host: 127.0.0.1
SOCKS5 Port: 1080
```

## Step 5: Test Internet Connectivity

Configure an application that supports SOCKS5 proxies to use:

```text
Proxy Type: SOCKS5
Address:    127.0.0.1
Port:       1080
```

Attempt to access the internet.

If the connection works, the Android relay and Windows bridge are communicating successfully.

You can now proceed to system-wide internet sharing.

---

# System-Wide Internet Sharing

The project supports system-wide Windows internet connectivity using **tun2socks** and **Wintun**.

These components enable applications that do not natively support SOCKS5 proxies to communicate through the Android gateway.

Once both dependency installers have completed successfully, subsequent connections are much simpler.

## Starting the Connection

### Android

Open Termux and navigate to the project folder.

```bash
cd "/path/to/your/folder"
```

Start the Android relay:

```bash
python android_relay.py
```

Leave it running.

### Windows

Open PowerShell as Administrator.

Navigate to the project folder.

Run:

```powershell
.\start_full_tunnel.bat
```

The startup script launches the configured system-wide networking components.

Your Windows computer should now route supported internet traffic through the Android relay.

**Keep the Android relay running while the connection is active.**

---

# Stopping the Connection

On Windows, open PowerShell as Administrator.

Navigate to your project directory and execute:

```powershell
.\stop_full_tunnel.bat
```

This stops the full-tunnel configuration.

If necessary, stop the Android relay by pressing:

```text
CTRL+C
```

inside Termux.

---

# Restarting the Connection

If the relay disconnects or you unplug your phone, restart both ends of the connection.

### Android

Stop the existing Python process:

```text
CTRL+C
```

Navigate to your project directory:

```bash
cd "/path/to/your/folder"
```

Restart the relay:

```bash
python android_relay.py
```

### Windows

Open PowerShell as Administrator.

Stop the previous tunnel:

```powershell
.\stop_full_tunnel.bat
```

Start a new tunnel:

```powershell
.\start_full_tunnel.bat
```

---

# Project Files

| File                    | Description                                                                    |
| ----------------------- | ------------------------------------------------------------------------------ |
| `android_relay.py`      | Android-side network relay responsible for forwarding traffic to the internet. |
| `windows_bridge.py`     | Windows-side SOCKS5 bridge that communicates with Android over ADB.            |
| `setup_termux.sh`       | Installs/configures the required Android-side dependencies in Termux.          |
| `setup_windows.bat`     | Installs/configures the required Windows-side dependencies.                    |
| `start_bridge.bat`      | Starts the basic Windows bridge and configures ADB forwarding.                 |
| `stop_bridge.bat`       | Removes the configured ADB port forwarding.                                    |
| `start_full_tunnel.bat` | Starts the system-wide Windows internet tunnel.                                |
| `stop_full_tunnel.bat`  | Stops the system-wide Windows internet tunnel.                                 |

---

# Hotspot Throttling and Data Usage

### Why USB Debugging?

Android typically provides internet sharing through native USB tethering or Wi-Fi hotspot functionality.

These mechanisms may be subject to carrier-specific hotspot allowances, usage accounting, and speed restrictions.

This project instead uses an application-level networking relay carried through USB debugging.

**The key difference is that Android's native tethering interface is never activated.**

### Observed Behavior

During development and testing, this approach successfully avoided the hotspot-specific throttling and consumption tracking encountered when using conventional tethering.

The Windows computer accesses the internet through the phone's active mobile connection without enabling Android's native tethering interface.

However, results may vary depending on:

* Mobile carrier
* Android version
* Cellular data plan
* Device configuration
* Network traffic classification

**Disclaimer:** Avoiding Android's native hotspot accounting does not guarantee that a carrier cannot identify, classify, or meter relayed traffic as tethering. This project does not guarantee unrestricted speeds or exemption from service-provider policies.

---

# Performance Considerations

### Connection Speed

Internet speed depends on several factors:

* Cellular signal strength
* Carrier network performance
* USB connection quality
* ADB forwarding throughput
* Python processing overhead
* SOCKS5 proxy overhead
* Virtual network interface performance

Under favorable conditions, the relay can deliver speeds comparable to the phone's normal mobile connection.

Performance is not guaranteed to match native tethering.

### UDP and Gaming

UDP packets are encapsulated in TCP for transmission through the ADB connection.

This can introduce additional latency during packet loss or congestion.

Because TCP provides ordered delivery, one delayed segment may temporarily block subsequent encapsulated UDP packets.

Consequently, some real-time applications may experience:

* Higher latency
* Additional jitter
* Delayed UDP packet delivery

For general web browsing, downloads, and many other applications, this may have a limited practical impact.

---

# Security

The relay is designed to operate locally through USB debugging.

The Windows SOCKS5 endpoint binds to:

```text
127.0.0.1:1080
```

The ADB forwarding connection uses:

```text
127.0.0.1:19090
```

The configuration avoids intentionally exposing the SOCKS5 proxy to the local Wi-Fi or LAN.

### Security Recommendations

* Only authorize USB debugging connections to trusted computers.
* Disable USB debugging when it is no longer needed.
* Avoid exposing the relay to external network interfaces.
* Keep Python and your networking dependencies updated.
* Do not run untrusted modifications to the relay scripts.

---

# Troubleshooting

### Windows Does Not Detect Android

Run:

```powershell
adb devices
```

Verify that:

* USB debugging is enabled.
* The USB cable supports data transfer.
* The phone is unlocked.
* The computer has been authorized.
* ADB is installed and accessible.

If necessary, restart the ADB server:

```powershell
adb kill-server
adb start-server
adb devices
```

### SOCKS5 Proxy Cannot Connect

Check that:

1. `android_relay.py` is running on Android.
2. ADB recognizes the Android device.
3. Port forwarding is configured.
4. `windows_bridge.py` is running.
5. No other application is occupying the configured ports.

Reconfigure forwarding if necessary:

```powershell
adb forward tcp:19090 tcp:19090
```

### Windows Has No Internet

First verify that the basic SOCKS5 proxy works.

If the proxy works but system-wide internet sharing fails, check:

* tun2socks configuration
* Wintun availability
* Windows routing configuration
* Administrator permissions
* DNS configuration
* Firewall restrictions

Stop the full tunnel before troubleshooting Windows network routes:

```powershell
.\stop_full_tunnel.bat
```

### Android Stops the Relay

Android may suspend background processes to conserve battery.

Disable battery optimization for Termux or Pydroid if the operating system repeatedly terminates the relay.

Keep the relay application active when using the connection.

# Technical Overview

This project demonstrates several networking and systems-programming concepts:

* Python socket programming
* SOCKS5 proxy implementation
* Android Debug Bridge integration
* TCP connection forwarding
* UDP encapsulation and decapsulation
* Framed network protocols
* Virtual networking through Wintun
* IP-to-SOCKS traffic conversion
* Windows route configuration
* Cross-platform process communication

Unlike a conventional hotspot utility, the gateway implements its own application-level traffic forwarding pipeline between Windows and Android.

---

## Disclaimer

This software is provided for educational, experimental, and personal networking purposes.

Carrier policies regarding tethering, hotspot allowances, and network usage may apply regardless of the transport mechanism used.

Users are responsible for complying with their service agreements and applicable laws.

---

### Phone USB Internet Gateway

**Your phone. Your connection. Your gateway.**
