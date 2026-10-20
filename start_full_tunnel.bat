@echo off
setlocal
cd /d "%~dp0"

fltmc >nul 2>&1
if errorlevel 1 (
  echo ERROR: Run this BAT file as Administrator.
  pause
  exit /b 1
)

where adb >nul 2>&1
if errorlevel 1 (
  echo ERROR: adb.exe is not in PATH.
  pause
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3 is not in PATH.
  pause
  exit /b 1
)

if not exist "%~dp0tun2socks.exe" (
  echo ERROR: Put tun2socks.exe in this folder.
  pause
  exit /b 1
)

if not exist "%~dp0wintun.dll" (
  echo ERROR: Put the correct-architecture wintun.dll in this folder.
  pause
  exit /b 1
)

echo Checking Android connection...
adb devices
echo.
adb forward --remove tcp:19090 >nul 2>&1
adb forward tcp:19090 tcp:19090
if errorlevel 1 (
  echo ERROR: ADB forward failed. Check USB debugging authorization.
  pause
  exit /b 1
)

echo Starting local Windows SOCKS bridge...
start "Phone USB Gateway - Bridge" cmd /k python "%~dp0windows_bridge.py"
timeout /t 2 /nobreak >nul

echo Starting tun2socks...
start "Phone USB Gateway - tun2socks" "%~dp0tun2socks.exe" --device wintun --proxy socks5://127.0.0.1:1080
timeout /t 3 /nobreak >nul

netsh interface show interface | findstr /I /C:"wintun" >nul
if errorlevel 1 (
  echo ERROR: The wintun interface did not appear.
  echo Check the tun2socks window for an error.
  pause
  exit /b 1
)

echo Configuring Wintun...
netsh interface ipv4 set address name="wintun" source=static addr=192.168.123.1 mask=255.255.255.0
netsh interface ipv4 set interface interface="wintun" metric=1
netsh interface ipv4 set dnsservers name="wintun" static address=1.1.1.1 register=none validate=no

REM Active-only route: removed on reboot and removable with stop_full_tunnel.bat.
netsh interface ipv4 delete route 0.0.0.0/0 "wintun" 192.168.123.1 >nul 2>&1
netsh interface ipv4 add route 0.0.0.0/0 "wintun" 192.168.123.1 metric=1 store=active

echo.
echo ==========================================================
echo Full IPv4 tunnel should now be active.
echo PC -^> Wintun -^> local SOCKS -^> ADB USB -^> Android -^> Internet
echo ==========================================================
echo.
echo IMPORTANT:
echo - Leave android_relay.py running in Pydroid.
echo - Turn phone Wi-Fi OFF to force Android to use cellular.
echo - Leave both Windows command windows open.
echo - Run stop_full_tunnel.bat when finished.
echo.
pause
