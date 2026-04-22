@echo off
setlocal EnableDelayedExpansion

set INSTALL_DIR=%APPDATA%\VdiskUploader
set EXE_NAME=VdiskUploader.exe
set EXE_PATH=%INSTALL_DIR%\%EXE_NAME%

echo ============================================
echo  Vdisk Uploader - Installer
echo ============================================
echo.

echo [1/3] Copying files to %INSTALL_DIR%...
mkdir "%INSTALL_DIR%" 2>nul
xcopy /E /I /Y /Q "%~dp0." "%INSTALL_DIR%" > nul
if errorlevel 1 (
    echo ERROR: File copy failed.
    pause & exit /b 1
)

echo [2/3] Creating desktop shortcut...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Vdisk Uploader.lnk'); $s.TargetPath = '%EXE_PATH%'; $s.Arguments = 'run'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'Vdisk Clipboard Uploader'; $s.Save()" > nul

echo [3/3] Registering autostart...
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v VdiskUploader /t REG_SZ /d "\"%EXE_PATH%\" run" /f > nul

echo.
echo ============================================
echo  Installation complete!
echo  Location : %INSTALL_DIR%
echo  Shortcut : Desktop\Vdisk Uploader
echo  Autostart: Registered
echo ============================================
echo.
start "" "%EXE_PATH%" run
pause
