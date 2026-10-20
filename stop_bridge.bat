@echo off
echo Removing ADB forwarding...
adb forward --remove tcp:19090
echo.
echo Also close:
echo   - the windows_bridge.py window
echo   - tun2socks.exe
echo and restore the Windows routes if you enabled TUN routing.
pause
