#!/data/data/com.termux/files/usr/bin/bash
# Android USB SOCKS5 Relay - Termux dependency installer.
# Run from Termux (not adb shell, Pydroid, or a regular Android shell).
# Does not turn on hotspot/tethering or start the relay.
set -euo pipefail

if [[ "${PREFIX:-}" != /data/data/com.termux/files/usr ]] || ! command -v pkg >/dev/null 2>&1; then
  echo 'ERROR: Run this script inside the Termux app.' >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
printf '%s\n' '=======================================================' ' Android USB SOCKS5 Relay - Termux setup' '======================================================='
echo '[1/3] Updating Termux package index ...'
pkg update -y

echo '[2/3] Installing Python and pip ...'
pkg install -y python python-pip

python -c 'import sys, socket, selectors; print("Python:", sys.version.split()[0]); print("socket and selectors: OK")'
python -m pip --version

echo '[3/3] Installing optional Android-specific Python dependencies ...'
if [[ -f "$SCRIPT_DIR/requirements-termux.txt" ]]; then
  python -m pip install -r "$SCRIPT_DIR/requirements-termux.txt"
elif [[ -f "$SCRIPT_DIR/requirements-android.txt" ]]; then
  python -m pip install -r "$SCRIPT_DIR/requirements-android.txt"
else
  echo 'None required: android_relay.py uses Python standard-library modules.'
fi

printf '\n%s\n' '=======================================================' ' Termux dependencies installed successfully.' '======================================================='
if [[ -f "$SCRIPT_DIR/android_relay.py" ]]; then
  printf 'Start the phone relay with:\n  cd %q && python android_relay.py\n' "$SCRIPT_DIR"
else
  echo 'Copy android_relay.py into your Termux home directory first.'
  echo 'Then run: python ~/android_relay.py'
fi
echo 'Keep the Termux session running while the PC connects over ADB.'
echo 'Enable USB debugging and approve the PC on your phone.'
echo 'This installer does NOT enable tethering or alter network routes.'
