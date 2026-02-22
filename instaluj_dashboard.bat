@echo off
chcp 65001 >nul
REM SofikaMax Agent - instalacja Dashboardu (Streamlit + pandas)
REM Dwuklik na ten plik - zainstaluje pakiety i zamknie okno.

cd /d "%~dp0"

echo ============================================
echo  Instalacja Dashboardu - SofikaMax Agent
echo ============================================
echo.

py -m pip install --upgrade pip
py -m pip install -r requirements-dashboard.txt

if errorlevel 1 (
    echo.
    echo Blad instalacji. Sprobuj recznie w konsoli:
    echo   py -m pip install streamlit pandas
    echo.
    pause
    exit /b 1
)

echo.
echo Gotowe. Teraz kliknij "Otworz Dashboard" w aplikacji SofikaMax Agent.
echo.
pause
