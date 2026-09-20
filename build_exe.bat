@echo off
REM ===================================================================
REM  ដំណើរការឯកសារនេះពី folder គម្រោង (កន្លែងតែមួយនឹង app.py)
REM  ក្នុង terminal ដែល virtualenv របស់អ្នកបានបើកដំណើរការរួច
REM ===================================================================

echo កំពុងបិទដំណើរការកម្មវិធី .exe ឬ Command Prompt ចាស់ៗដែលកំពុងបើកចោល...
taskkill /f /im docsystem.exe >nul 2>&1
taskkill /f /im cmd.exe /fi "WINDOWTITLE eq *docsystem*" >nul 2>&1

echo.
echo កំពុងដំឡើង PyInstaller...
pip install pyinstaller

echo.
echo កំពុង package ជា .exe (អាចចំណាយពេលពីរបីនាទី)...
echo.

python -m PyInstaller ^
    --name docsystem ^
    --onedir ^
    --noconfirm ^
    --noconsole ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --hidden-import engineio.async_drivers.threading ^
    --hidden-import sqlalchemy.dialects.postgresql ^
    --hidden-import psycopg2 ^
    --copy-metadata python-engineio ^
    --copy-metadata python-socketio ^
    --copy-metadata Flask-SocketIO ^
    --copy-metadata werkzeug ^
    --collect-all google.genai ^
    run_desktop.py

echo.
echo Copying Tesseract portable folder...
xcopy /E /I /Y tesseract dist\docsystem\tesseract

echo.
echo Copying templates, static and .env to dist\docsystem...
xcopy /E /I /Y templates dist\docsystem\templates
xcopy /E /I /Y static dist\docsystem\static
copy /Y .env dist\docsystem\.env

echo.
echo ===================================================================
echo បញ្ចប់! docsystem.exe និងឯកសារចាំបាច់ទាំងអស់ត្រូវបានរៀបចំរួចរាល់ក្នុង dist\docsystem\
echo ===================================================================
pause