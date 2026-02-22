# Reguły instytucjonalne – SofikaMax Agent

Dokument opisuje zasady przyjęte pod kątem **zarządzania kapitałem jak w banku/funduszu**: maksymalizacja zysków przy kontroli ryzyka, bez wymuszania transakcji.

---

## 1. Limity ekspozycji (config)

| Parametr | Domyślnie | Znaczenie |
|----------|-----------|-----------|
| `MAX_POSITIONS_TOTAL` | 5 | Maksymalna liczba równoczesnych pozycji |
| `MAX_POSITIONS_IN_GROUP` | 2 | Maks. pozycji w jednej grupie korelacyjnej (np. AUD+CAD) |
| `MAX_EXPOSURE_PCT_CURRENCY` | 10% | Maks. łącznie % kapitału na jedną walutę (rekomendacja) |

Ekspozycja grupowa jest liczona w `risk_engine`; przekroczenie generuje ostrzeżenia i rekomendację „WCHODŹ Z OGRANICZENIAMI”.

---

## 2. Conviction i otwieranie pozycji

- **80–100 pkt → HIGH** – można otwierać, pełny sugerowany size (do ~1.5% kapitału).
- **60–79 pkt → MODERATE** – można otwierać, zmniejszony size (~0.7×).
- **40–59 pkt → LOW** – **tylko watchlist**; nie otwieraj nowej pozycji.
- **0–39 pkt → PASS** – **nie handluj**; brak konfluencji warstw.

W raporcie w sekcji „Jeśli wchodzisz” pokazywane są **tylko** setupy HIGH i MOD. NISKI i PASS nie wchodzą do top_ideas.

---

## 3. Kary (penalty) – kiedy obniżamy scoring

- Wydarzenie wysokiej wagi (FOMC/CPI/NFP &lt; 24–72h): **-15**
- Dywergencja (np. COT pro-USD, US10Y spada): **-10**
- OI spada mimo ruchu (short covering / wydech): **-10**
- Range regime na Weekly: **-10**

Event **KRYTYCZNY** → decyzja **NIE WCHODŹ** (agent chroni kapitał).

---

## 4. Sugerowany size (% kapitału)

Zależny od: conviction (HIGH/MOD/LOW), jakości historycznej setupu, ryzyka eventowego.

- Event KRYTYCZNY → mocna redukcja lub „nie wchodź”.
- PASS / brak conviction → **0%** (tylko watchlist).
- NISKI → max 0.5× bazy; HIGH → do 1.0× (z limitem np. 1.5% na pozycję).

---

## 5. Risk disclosure (dlaczego system może nie działać)

System wyświetla w raporcie i w payloadzie krótki disclosure:

1. Lag COT (dane z wtorku).
2. Nagłe zmiany makro.
3. Instytucje uśredniają pozycje.
4. Fałszywy flip bez kontynuacji.
5. Range regime mimo momentum.
6. Hedge distortion (Commercials).
7. Brak płynności przy ekstremach.

**„COT is contextual, not predictive.”**

---

## 6. Rekomendacja risk_engine

W podsumowaniu RISK & PORTFOLIO zawsze jest:

- Max X równoczesnych pozycji, max 2 w grupie.
- **Max 10% kapitału łącznie na jedną walutę** (rekomendacja).
- Ostrzeżenia przy przekroczeniu limitów grupowych.

---

## 7. Zgodność ze specyfikacją GLOBAL MACRO COT ENGINE 3.0

Architektura 6 warstw (COT, Regime, Flow, Surprise, Sentiment, News), progi conviction 80/60/40, kary event/div/OI/range oraz zasady exposure control są z nią zgodne. Surprise i News zastępują osobną warstwę „Technical Location”; lokalizacja HTF jest częściowo w Regime (40 EMA, HH/HL, ATR).
