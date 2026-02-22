Ikona SofikaMax przy uruchomieniu
=================================

W Windows plik .bat NIE MOZE miec wlasnej ikony – zawsze ma ikone „zebatki”.
Ikone z logo SofikaMax ma SKROT (.lnk).

Co zrobiono:
- assets/sofikamax_logo.ico – ikona wygenerowana z logo (PNG -> ICO)
- W folderze c:\TradingAgent jest skrot: "Uruchom SofikaMax Agent.lnk" z ta ikona

Jak uzyc:
1. Otworz folder c:\TradingAgent.
2. Znajdz plik "Uruchom SofikaMax Agent.lnk" (ma ikone Sofika Max).
3. Przeciagnij go na Pulpit (albo PPM -> Wyslij do -> Pulpit (utworz skrot)).
4. Odpalaj DALEJ ten skrot – uruchomi sie dashboard, a w Eksploratorze widac logo SofikaMax.

Aby odswiezyc ikone skrotu (np. po zmianie logo):
  powershell -ExecutionPolicy Bypass -File "utilities\utworz_skrot_sofikamax.ps1"
