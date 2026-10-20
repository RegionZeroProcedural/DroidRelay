@echo off
setlocal
cd /d "%~dp0"

fltmc >nul 2>&1
if errorlevel 1 (
  echo ERROR: Run this BAT file as Administrator.
  pause
  exit /b 1
)

echo Removing Wintun default route...
netsh interface ipv4 delete route 0.0.0.0/0 "wintun" 192.168.123.1 >nul 2>&1

echo Removing ADB forwarding...
adb forward --remove tcp:19090 >nul 2>&1

echo.
echo Close the windows titled:
echo   Phone USB Gateway - Bridge
echo   Phone USB Gateway - tun2socks
echo.
echo The original Windows network route was never deleted, so after the
echo Wintun route is removed Windows should immediately use it again.
pause
