@echo off
setlocal EnableDelayedExpansion

echo ============================================
echo  Vdisk Uploader - Build Script
echo ============================================
echo.

echo [1/5] Checking PyInstaller...
pip show pyinstaller > nul 2>&1
if errorlevel 1 (
    pip install pyinstaller --system-certs
    if errorlevel 1 (
        echo ERROR: PyInstaller install failed.
        pause & exit /b 1
    )
)

echo [2/5] Cleaning previous build...
rmdir /S /Q dist  2>nul
rmdir /S /Q build 2>nul

echo [3/5] Building exe...
pyinstaller VdiskUploader.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause & exit /b 1
)

echo [4/5] Copying Playwright Chromium browsers...
set BROWSERS_SRC=%USERPROFILE%\AppData\Local\ms-playwright
set BROWSERS_DST=dist\VdiskUploader\playwright_browsers

if not exist "%BROWSERS_SRC%" (
    echo ERROR: Playwright browsers not found at %BROWSERS_SRC%
    echo Run: playwright install chromium
    pause & exit /b 1
)

mkdir "%BROWSERS_DST%" 2>nul
set FOUND=0
for /D %%i in ("%BROWSERS_SRC%\chromium*" "%BROWSERS_SRC%\ffmpeg*" "%BROWSERS_SRC%\winldd*") do (
    echo   Copying %%~ni...
    xcopy /E /I /Y /Q "%%i" "%BROWSERS_DST%\%%~ni" > nul
    set FOUND=1
)
if "!FOUND!"=="0" (
    echo ERROR: Chromium folder not found in %BROWSERS_SRC%
    pause & exit /b 1
)

echo [5/5] Copying install.bat...
copy /Y install.bat dist\VdiskUploader\install.bat > nul

echo.
echo ============================================
echo  Build complete!
echo  Output: dist\VdiskUploader\
echo  Zip the dist\VdiskUploader\ folder and distribute.
echo  Users run install.bat after unzipping.
echo ============================================
echo.
pause
