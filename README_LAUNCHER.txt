========================================
SofikaMax Agent - Uruchomienie z pulpitu
========================================

START DOMYSLNY (cichy - tylko Dashboard):

  1. Dwuklik: Uruchom_SofikaMax_Agent.vbs  (najlepiej skrot na pulpicie)
     Efekt: po kilku sekundach przegladarka z Dashboardem, zadnych okien.
  2. Jesli .vbs wyskakuje blad (np. Windows Script Host):
     - Utworz skrot na pulpicie.
     - Cel skrotu:  powershell.exe
     - Argumenty:   -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\TradingAgent\Uruchom_SofikaMax_Agent.ps1"
     - Katalog roboczy:  C:\TradingAgent
     Odpalaj ten skrot zamiast .vbs.
  3. Uruchom_SofikaMax_Agent.bat tez uruchamia .vbs (moze na chwile pojawic sie czarne okno CMD).


PANEL Z PRZYCISKAMI (Telegram, harmonogram, raport w konsoli):

  W folderze TradingAgent:  py launcher.py

Wymagania: Python (pythonw w PATH), streamlit (requirements-dashboard.txt).
