@echo off
echo Removing the temporary Wintun route...
netsh interface ipv4 delete route 0.0.0.0/0 "wintun" 192.168.123.1
echo Removing ADB port forward...
adb forward --remove tcp:19090
echo Done. If networking still looks wrong, reboot Windows.
pause
