@echo off
setlocal
cd /d "%~dp0"

echo === Phone USB Gateway ===
echo.
echo 1. Make sure android_relay.py is already running in Pydroid.
echo 2. Make sure USB debugging is enabled and authorized.
echo.

where adb >nul 2>&1
if errorlevel 1 (
  echo ERROR: adb.exe is not in PATH.
  echo Install Android Platform Tools and add its folder to PATH,
  echo or put this BAT file in the same folder as adb.exe.
  pause
  exit /b 1
)

echo Checking phone...
adb devices
echo.
adb forward --remove tcp:19090 >nul 2>&1
adb forward tcp:19090 tcp:19090
if errorlevel 1 (
  echo ERROR: Could not create ADB forward.
  pause
  exit /b 1
)

echo ADB forwarding active: PC 127.0.0.1:19090 -^> phone 127.0.0.1:19090
echo.
echo Starting Windows SOCKS bridge in a new window...
start "Phone USB Gateway - Bridge" cmd /k python "%~dp0windows_bridge.py"

echo.
echo The SOCKS5 endpoint is now:
echo     127.0.0.1:1080
echo.
echo Test the SOCKS bridge before enabling tun2socks.
pause
