# Konwersja logo PNG do ICO (dla ikony skrotu Windows).
# Uruchom raz: py utilities/png_to_ico.py

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

LOGO_PNG = os.path.join(ROOT, "assets", "sofikamax_logo.png")
LOGO_ICO = os.path.join(ROOT, "assets", "sofikamax_logo.ico")
SIZES = [(16, 16), (32, 32), (48, 48), (256, 256)]


def main():
    try:
        from PIL import Image
    except ImportError:
        print("Zainstaluj Pillow: py -m pip install Pillow")
        sys.exit(1)
    if not os.path.isfile(LOGO_PNG):
        print(f"Brak pliku: {LOGO_PNG}")
        sys.exit(1)
    img = Image.open(LOGO_PNG)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")
    os.makedirs(os.path.dirname(LOGO_ICO), exist_ok=True)
    img.save(LOGO_ICO, format="ICO", sizes=SIZES)
    print(f"Zapisano: {LOGO_ICO}")


if __name__ == "__main__":
    main()
