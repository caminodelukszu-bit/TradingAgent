import requests

url = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
r = requests.get(url + "?$limit=2", timeout=20)
print("Status:", r.status_code)
if r.status_code == 200:
    d = r.json()
    if d:
        print("Kolumny:", list(d[0].keys())[:20])
    else:
        print("Pusta odpowiedz")
else:
    print("Blad:", r.text[:300])