@echo off
REM SofikaMax Agent - uruchomienie Dashboardu (Streamlit)
REM Dwuklik na ten plik lub: run_dashboard.bat

cd /d "%~dp0"

echo Uruchamiam Dashboard na http://localhost:8501 ...
echo.
py -m streamlit run dashboard.py
if errorlevel 1 (
    echo.
    echo Blad uruchomienia. Zainstaluj zaleznosci: py -m pip install -r requirements-dashboard.txt
    pause
)
