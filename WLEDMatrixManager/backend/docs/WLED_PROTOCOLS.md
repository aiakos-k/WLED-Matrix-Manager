# WLED Protokoll-Referenz

Dieses Dokument beschreibt die zwei Kommunikationsprotokolle, die wir mit WLED-Geräten verwenden,
basierend auf dem [WLED Firmware-Quellcode](https://github.com/wled/WLED/blob/main/wled00/udp.cpp)
und der offiziellen Dokumentation.

---

## 1. JSON API (HTTP)

**Endpoint:** `POST http://<IP>/json/state`
**Doku:** https://kno.wled.ge/interfaces/json-api/

### Wie wir es nutzen

Wir senden JSON-Objekte um LEDs per Per-Segment Individual LED Control (`seg.i`) zu steuern.
Das ist die "sichere" Methode — kein Flash, supports transition, volle Kontrolle.

### Unser Command-Format

```json
{
  "on": true,
  "bri": 128,
  "transition": 0,
  "seg": {
    "id": 0,
    "i": [0, [255, 0, 0], 1, [0, 255, 0]]
  }
}
```

### Wichtige State-Properties

| Property | Typ | Beschreibung |
|----------|-----|-------------|
| `on` | bool | An/Aus. `"t"` zum togglen |
| `bri` | 0-255 | Master-Brightness. **Wenn `on: false`, enthält es die letzte Brightness** |
| `transition` | 0-65535 | Crossfade-Dauer in 100ms-Einheiten. `0` = sofort |
| `tt` | 0-65535 | Einmal-Transition nur für diesen API-Call |
| `live` | bool | **Erzwingt Realtime-Mode und blankt LEDs.** Kein Timeout! Muss mit `{"live":false}` beendet werden |
| `lor` | 0/1/2 | Live data override. 0=off, 1=bis live endet, 2=bis Reboot |
| `seg.i` | array | Individuelles LED-Array. Format: `[index, [R,G,B], ...]` oder Ranges `[start, stop, [R,G,B]]` |

### Segment-LEDs (`seg.i`) Format

Drei Varianten:

```json
// Einzelne LEDs
{"seg":{"i":["FF0000","00FF00","0000FF"]}}

// Mit explizitem Index
{"seg":{"i":[0,"FF0000", 2,"00FF00", 4,"0000FF"]}}

// Ranges (start bis stop-1)
{"seg":{"i":[0, 8, "FF0000", 10, 18, "0000FF"]}}
```

**Hinweis:** LED-Indizes sind Segment-basiert (LED 0 = erste LED des Segments).

### Brightness-Interaktion

> "For your colors to apply correctly, make sure the desired brightness is set beforehand.
> Turning on the LEDs from an off state and setting individual LEDs in the same JSON request will not work!"

→ Deshalb setzen wir `"on": true, "bri": X` im selben Command zusammen mit `seg.i`.

---

## 2. UDP Realtime — DNRGB Protokoll

**Port:** 21324 (Standard WLED UDP-Port)
**Doku:** https://kno.wled.ge/interfaces/udp-realtime/

### Protokolltypen auf Port 21324

| Byte 0 | Protokoll | Max LEDs |
|--------|-----------|----------|
| 0 | WLED Notifier (Sync) | - |
| 1 | WARLS | 255 |
| 2 | DRGB | 490 |
| 3 | DRGBW | 367 |
| **4** | **DNRGB** ← wir nutzen das | **489/Paket** |
| 5 | DNRGBW | - |

### DNRGB Paketformat

```
Byte 0:    4 (Protokoll-ID für DNRGB)
Byte 1:    Timeout in Sekunden (1-254, 255 = kein Timeout / indefinite)
Byte 2:    Start-LED-Index High-Byte
Byte 3:    Start-LED-Index Low-Byte
Byte 4+:   [R, G, B, R, G, B, ...] Pixeldaten ab Start-Index
```

**Max Paketgröße:** 1472 Bytes (UDP_IN_MAXSIZE in WLED)
→ Header: 4 Bytes + 3 Bytes/LED = max **489 LEDs pro Paket**
→ Wir nutzen 458 LEDs/Paket (`MAX_LEDS_PER_PACKET`) als Sicherheitspuffer

### Timeout-Byte (Byte 1)

- `1-254`: Sekunden bis WLED automatisch Realtime-Mode verlässt
- `255`: Kein Timeout — bleibt in Realtime bis explizit beendet
- `0`: **Spezialwert — beendet Realtime sofort!**

Aus dem Quellcode:
```cpp
if (udpIn[1] == 0) {
    realtimeTimeout = 0;  // cancel realtime mode immediately
    return;
} else {
    realtimeLock(udpIn[1]*1000 + 1, REALTIME_MODE_UDP);
}
```

### Chunked Packets für große Matrizen

DNRGB unterstützt beliebig viele LEDs durch mehrere Pakete mit verschiedenen Start-Indizes:

```
Paket 1: [4, timeout, 0x00, 0x00, R,G,B, R,G,B, ...]  ← LEDs 0-457
Paket 2: [4, timeout, 0x01, 0xCA, R,G,B, R,G,B, ...]  ← LEDs 458-915
...
```

### WLED-Verarbeitung (aus udp.cpp)

```cpp
if (udpIn[0] == 4 && packetSize > 7) { // DNRGB
    unsigned id = ((udpIn[3] << 0) & 0xFF) + ((udpIn[2] << 8) & 0xFF00);
    for (size_t i = 4; i < packetSize - 2 && id < totalLen; i += 3, id++) {
        setRealtimePixel(id, udpIn[i], udpIn[i+1], udpIn[i+2], 0);
    }
}
// Nach allen Protokollen:
if (useMainSegmentOnly) strip.trigger();
else                    strip.show();
```

→ Die Pixel werden **nach dem realtimeLock()** gesetzt und dann per `strip.show()` angezeigt.

---

## 3. Realtime-Mode Lifecycle (Flash-Ursache & Lösung)

### Entry: `realtimeLock()` — Ursache des Flash

```cpp
void realtimeLock(uint32_t timeoutMs, byte md) {
    if (!realtimeMode && !realtimeOverride) {
        // ── Dieser Block läuft NUR beim ERSTEN Eintritt ──
        if (useMainSegmentOnly) {
            mainseg.clear();
            mainseg.freeze = true;
        } else {
            strip.fill(BLACK);   // Alle LEDs schwarz
        }
        if (briT == 0) {
            // Strip war AUS → letzte Brightness wiederherstellen
            strip.setBrightness(briLast, true);
        }
    }
    realtimeMode = md;
    if (arlsForceMaxBri) strip.setBrightness(255, true);
    // show() nur für GENERIC (JSON API), NICHT für UDP!
    if (briT > 0 && md == REALTIME_MODE_GENERIC) strip.show();
}
```

### Warum der Flash passiert

1. WLED zeigt aktuell einen Effekt (z.B. Rainbow) bei Brightness X
2. Erstes UDP-Paket kommt → `realtimeLock()` wird aufgerufen
3. `strip.fill(BLACK)` füllt den Buffer schwarz
4. **ABER:** Zwischen fill(BLACK) und dem tatsächlichen setRealtimePixel() + show()
   kann der WLED-Effekt-Loop noch einen Frame rendern → **Flash des alten Effekts**
5. Zusätzlich: `setBrightness(briLast)` stellt Brightness wieder her, falls Strip OFF war
6. `arlsForceMaxBri` in WLED-Settings kann Brightness auf 255 erzwingen

### Exit: `exitRealtime()`

```cpp
void exitRealtime() {
    strip.setBrightness(bri, true);  // Normale Brightness wiederherstellen
    realtimeTimeout = 0;
    realtimeMode = REALTIME_MODE_INACTIVE;
    strip.show();  // Zeigt den normalen Effekt wieder an
}
```

→ Wird automatisch aufgerufen wenn der Timeout abläuft.

### Lösung: Pre-Entry via JSON API `{"live":true}`

Die JSON API hat ein spezielles Property:

> **`live: true`** — enters realtime mode and blanks the LEDs

Wenn wir **vor dem ersten UDP-Paket** `{"live":true}` senden:

1. WLED geht sauber in `REALTIME_MODE_GENERIC` → LEDs werden geblackt
2. `strip.show()` wird aufgerufen (weil `md == REALTIME_MODE_GENERIC`) → Schwarz wird tatsächlich angezeigt
3. Timeout wird auf UINT32_MAX gesetzt (kein Auto-Exit)
4. Beim ersten UDP-Paket: `realtimeMode` ist bereits `true`
   → **Der Entry-Block wird komplett übersprungen** → Kein Flash!
5. UDP setzt Pixel → `show()` → Erstes Bild wird direkt angezeigt

**Wichtig:** Nach Playback-Ende müssen wir `{"live":false}` senden (oder der WLED-Timeout greift).

### WLED-Settings die Realtime beeinflussen

In WLED unter Settings → Sync:

| Setting | Bedeutung |
|---------|----------|
| **Force Max Brightness** (`arlsForceMaxBri`) | Erzwingt Brightness 255 im Realtime-Mode |
| **Realtime Timeout** (`realtimeTimeoutMs`) | Standard-Timeout für Realtime (wird durch `live:true` überschrieben) |
| **Use Main Segment Only** | Nur Hauptsegment für Realtime nutzen (freeze statt fill) |

---

## 4. Unsere Implementierung

### device_controller.py

| Methode | Beschreibung |
|---------|-------------|
| `send_json_command()` | HTTP POST auf `/json/state` via aiohttp |
| `generate_wled_command()` | Baut JSON mit `seg.i` aus Pixel-Daten (Range-Compression) |
| `send_udp_dnrgb()` | Sendet DNRGB-Pakete mit Chunking (458 LEDs/Paket) |
| `turn_off()` | `{"on": false, "bri": 255, "transition": 0}` — Brightness für nächstes Mal wiederherstellen |
| `check_health()` | GET auf `/json/info` |

### scene_playback.py

| Feature | Beschreibung |
|---------|-------------|
| `_enter_realtime_black()` | Sendet `{"live":true}` via JSON API um sauber in Realtime zu wechseln |
| `_playback_loop()` | Iteriert Frames und sendet per UDP DNRGB oder JSON API |
| Upscaling | `upscale_pixel_data()` skaliert Szenen-Auflösung auf Device-Auflösung |
| Device-Exclusivity | Nur eine Szene pro Device-IP gleichzeitig |

### Brightness-Kette

```
Frame-Brightness (0-255)
    ↓
    ├─ JSON API: "bri" Property (WLED Master-Brightness)
    │   → WLED wendet es global auf alle seg.i Pixel an
    │
    └─ UDP DNRGB: Brightness per Software in Pixel eingerechnet
        → Kein separates Brightness-Byte im DNRGB-Protokoll
        → Pixel = [R*factor, G*factor, B*factor]
```

---

## 5. Referenzen

- **WLED Firmware Source:** https://github.com/wled/WLED/blob/main/wled00/udp.cpp
- **UDP Realtime Doku:** https://kno.wled.ge/interfaces/udp-realtime/
- **JSON API Doku:** https://kno.wled.ge/interfaces/json-api/
- **UDP Sync/Notifier:** https://kno.wled.ge/interfaces/udp-notifier/
