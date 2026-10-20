@echo off
setlocal EnableExtensions DisableDelayedExpansion
REM Android USB SOCKS5 Relay - Windows x64 dependency installer.
REM Place this file beside windows_bridge.py and your start/stop BAT files.
REM Existing adb.exe, tun2socks.exe, and wintun.dll are never overwritten.
REM Does NOT change network routes or start the tunnel.

cd /d "%~dp0" || (echo ERROR: Could not enter the project directory. & exit /b 1)
set "RELAY_DIR=%CD%"
set "PYTHON_CMD="

echo =======================================================
echo   Android USB SOCKS5 Relay - Windows setup (x64)
echo =======================================================
echo Project: "%RELAY_DIR%"
echo.

if /I not "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    echo ERROR: This installer targets 64-bit x86 Windows.
    echo        Other Windows architectures need different binaries.
    exit /b 1
)

where powershell.exe >nul 2>&1
if errorlevel 1 (echo ERROR: Windows PowerShell is required. & exit /b 1)

REM 1. Python. Use an installed copy, otherwise install with winget.
echo [1/4] Checking Python 3.9+ ...
call :detect_python
if not defined PYTHON_CMD (
    where winget.exe >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python was not found and winget is not available.
        echo Install Python 3 from python.org, reopen Command Prompt, and rerun this file.
        exit /b 1
    )
    echo Installing Python 3.13 with winget ...
    winget install --id Python.Python.3.13 --exact --source winget --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (echo ERROR: Python installation failed. & exit /b 1)
    call :detect_python
    if not defined PYTHON_CMD (
        echo Python was installed but is not yet available in this terminal.
        echo Open a NEW terminal and run setup_windows.bat again.
        exit /b 1
    )
)
echo Python command: %PYTHON_CMD%

REM 2. Portable ADB from Google's official Platform-Tools archive.
REM Copy ADB and its runtime DLLs into the project so no PATH edit is needed.
echo.
echo [2/4] Checking Android Debug Bridge (ADB) ...
if exist "%RELAY_DIR%\adb.exe" if exist "%RELAY_DIR%\AdbWinApi.dll" if exist "%RELAY_DIR%\AdbWinUsbApi.dll" goto :adb_ready

echo Downloading Android SDK Platform-Tools from Google ...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $root=$env:RELAY_DIR; $tmp=Join-Path $env:TEMP ('adb-setup-'+[guid]::NewGuid().ToString('N')); New-Item -ItemType Directory -Path $tmp | Out-Null; try { $zip=Join-Path $tmp 'platform-tools.zip'; Invoke-WebRequest -UseBasicParsing -Uri 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile $zip; Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force; $srcdir=Join-Path $tmp 'platform-tools'; if(!(Test-Path -LiteralPath (Join-Path $srcdir 'adb.exe'))){ throw 'ADB archive missing adb.exe' }; Get-ChildItem -LiteralPath $srcdir -File | Where-Object { $_.Name -eq 'adb.exe' -or $_.Extension -eq '.dll' } | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $root -Force } } finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }"
if errorlevel 1 (echo ERROR: ADB installation failed. & exit /b 1)
:adb_ready
"%RELAY_DIR%\adb.exe" version
if errorlevel 1 (echo ERROR: ADB failed to run. & exit /b 1)

REM 3. Wintun (signed AMD64 DLL). Verify official SHA256 before extracting.
echo.
echo [3/4] Checking Wintun ...
if exist "%RELAY_DIR%\wintun.dll" goto :wintun_ready

echo Downloading signed Wintun 0.14.1 from wintun.net ...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $root=$env:RELAY_DIR; $tmp=Join-Path $env:TEMP ('wintun-setup-'+[guid]::NewGuid().ToString('N')); New-Item -ItemType Directory -Path $tmp | Out-Null; try { $zip=Join-Path $tmp 'wintun.zip'; Invoke-WebRequest -UseBasicParsing -Uri 'https://www.wintun.net/builds/wintun-0.14.1.zip' -OutFile $zip; $expected='07c256185d6ee3652e09fa55c0b673e2624b565e02c4b9091c79ca7d2f24ef51'; if((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ine $expected){ throw 'Wintun ZIP SHA256 mismatch' }; Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force; $dll=Get-ChildItem -LiteralPath $tmp -Filter 'wintun.dll' -File -Recurse | Where-Object { $_.FullName -match '[\\/]amd64[\\/]' } | Select-Object -First 1; if(-not $dll){ throw 'Cannot find AMD64 wintun.dll' }; Copy-Item -LiteralPath $dll.FullName -Destination (Join-Path $root 'wintun.dll') -Force } finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }"
if errorlevel 1 (echo ERROR: Wintun installation failed. & exit /b 1)
:wintun_ready
if not exist "%RELAY_DIR%\wintun.dll" (echo ERROR: wintun.dll is missing. & exit /b 1)
echo Wintun ready.

REM 4. tun2socks. Only download if the project does not already have one.
REM GitHub release SHA256 digest is checked when supplied by the release API.
echo.
echo [4/4] Checking tun2socks ...
if exist "%RELAY_DIR%\tun2socks.exe" goto :tun2socks_ready

echo Downloading tun2socks Windows AMD64 release from GitHub ...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $root=$env:RELAY_DIR; $tmp=Join-Path $env:TEMP ('tun2socks-setup-'+[guid]::NewGuid().ToString('N')); New-Item -ItemType Directory -Path $tmp | Out-Null; try { $headers=@{'User-Agent'='android-usb-relay-installer'}; $release=Invoke-RestMethod -Uri 'https://api.github.com/repos/xjasonlyu/tun2socks/releases/latest' -Headers $headers; $asset=$release.assets | Where-Object { $_.name -eq 'tun2socks-windows-amd64.zip' } | Select-Object -First 1; if(-not $asset){ throw 'Windows AMD64 tun2socks asset not found' }; $zip=Join-Path $tmp 'tun2socks.zip'; Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $zip; if($asset.digest -and $asset.digest -match '^sha256:([0-9a-fA-F]{64})$'){ if((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ine $Matches[1]){ throw 'tun2socks ZIP SHA256 mismatch' } }; Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force; $exe=Get-ChildItem -LiteralPath $tmp -Filter 'tun2socks*.exe' -File -Recurse | Select-Object -First 1; if(-not $exe){ throw 'tun2socks executable missing in archive' }; Copy-Item -LiteralPath $exe.FullName -Destination (Join-Path $root 'tun2socks.exe') -Force } finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }"
if errorlevel 1 (echo ERROR: tun2socks installation failed. & exit /b 1)
:tun2socks_ready
if not exist "%RELAY_DIR%\tun2socks.exe" (echo ERROR: tun2socks.exe is missing. & exit /b 1)
echo tun2socks ready.

REM Python relay scripts currently use the Python standard library.
REM If you later add requirements, install them automatically when present.
echo.
if exist "%RELAY_DIR%\requirements-windows.txt" (
    echo Installing Python requirements-windows.txt ...
    %PYTHON_CMD% -m pip install -r "%RELAY_DIR%\requirements-windows.txt"
    if errorlevel 1 (echo ERROR: pip installation failed. & exit /b 1)
) else (
    if exist "%RELAY_DIR%\requirements.txt" (
        echo Installing Python requirements.txt ...
        %PYTHON_CMD% -m pip install -r "%RELAY_DIR%\requirements.txt"
        if errorlevel 1 (echo ERROR: pip installation failed. & exit /b 1)
    ) else (
        echo No Windows pip requirements file; standard-library Python is sufficient.
    )
)

echo.
echo =======================================================
echo Windows dependencies installed successfully.
echo ADB:       "%RELAY_DIR%\adb.exe"
echo Wintun:    "%RELAY_DIR%\wintun.dll"
echo tun2socks: "%RELAY_DIR%\tun2socks.exe"
echo.
echo Next: Enable USB debugging on Android, authorize your PC,
echo then run your existing start_bridge.bat or start_full_tunnel.bat.
echo Full-tunnel mode may require Run as administrator.
echo This installer did NOT change routes or enable the tunnel.
echo =======================================================
exit /b 0

:detect_python
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1
if not errorlevel 1 (set "PYTHON_CMD=py -3" & exit /b 0)
python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1
if not errorlevel 1 (set "PYTHON_CMD=python" & exit /b 0)
exit /b 1
