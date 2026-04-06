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

### Lösung: "Solid Black Effect" vor UDP-Start ✅

Nach vielen Iterationen (10+) hat sich folgende Strategie als einzig zuverlässige Lösung erwiesen:

**Vor dem ersten UDP-Frame:**
```json
{"transition": 0, "seg": {"fx": 0, "col": [[0, 0, 0]]}}
```

Dann **300ms warten**, bevor das erste UDP-Paket gesendet wird.

#### Warum das funktioniert

1. Der Effekt wird auf **Solid (fx:0)** mit Farbe **Schwarz** gesetzt
2. `transition: 0` → sofort, kein Crossfade
3. WLED rendert innerhalb weniger Effekt-Cycles (33ms bei 30fps) schwarze Pixel
4. 300ms Wartezeit gibt WS2812B genug Zeit für 2+ vollständige `show()`-Durchgänge
   (4096 LEDs × 30µs/LED = ~123ms pro show)
5. Wenn das erste UDP-Paket `realtimeLock()` auslöst und der Effekt-Loop noch einen
   letzten Frame rendert → dieser ist **Solid Schwarz** → kein sichtbarer Flash

#### Was NICHT funktioniert hat (und warum)

| Versuch | Problem |
|---------|---------|
| `{"live": true}` vor UDP | Setzt Realtime ohne Timeout. `turn_off()` am Ende wird ignoriert (Device bleibt im Realtime). `{"live":false}` verursacht End-Flash durch `exitRealtime()`. |
| `{"on":true, "bri":255, "live":true}` atomar | WLED verarbeitet `on`+`bri` VOR `live` in `deserializeState()` → Effekt rendert einen Frame bei voller Helligkeit → Flash sogar stärker |
| `{"on":false}` → UDP → `{"on":true}` | UDP bei ausgeschaltetem Device triggert trotzdem `realtimeLock()` mit `setBrightness(briLast)`. Das `on:true` danach triggert `colorUpdated()` → alter Effekt flasht kurz |
| Mehrere schwarze UDP-Pre-Frames | Flash passiert beim ERSTEN UDP-Paket in `realtimeLock()`. Weitere Frames kommen zu spät — der Effekt-Loop hat bereits gerendert |
| `{"on":true, "bri":255, "seg":{"fx":0, "col":[[0,0,0]]}}` | `on`+`bri` werden VOR `seg` verarbeitet. Für einen Frame rendert WLED den alten Effekt bei neuer Brightness |

#### Warum NUR `seg`-Änderung funktioniert

WLED's `deserializeState()` verarbeitet Properties in dieser Reihenfolge:
1. `on`, `bri` → State-Änderungen, lösen `colorUpdated()` aus → Effekt rendert
2. `transition` → Übergangszeit
3. `seg` → Segment-Properties (Effekt, Farbe, etc.)

Wenn man `on`/`bri` weglässt und NUR `seg` ändert, wird kein State-Change getriggert
der den alten Effekt rendert. Der Effekt wechselt direkt auf Solid Black.

### Playback-Ende: Einfaches `turn_off()` ✅

```json
{"on": false}
```

Am Ende der Scene-Playback reicht ein einfaches `turn_off()`. Der UDP Realtime-Timeout
(typisch 5 Sekunden) läuft natürlich ab. `exitRealtime()` ruft dann `setBrightness(bri)`
und `show()` auf — aber da das Device bereits OFF ist (`bri=0`), zeigt `show()` nichts an.

**Kein `send_udp_cancel()` oder `{"live":false}` nötig** — beides löst `exitRealtime()`
sofort aus, was den gespeicherten Effekt kurz anzeigen kann bevor `turn_off()` greift.

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
| `send_udp_cancel()` | Sendet `[4,0,0,0]` — DNRGB mit timeout=0 um Realtime sofort zu beenden |
| `turn_off()` | `{"on": false}` — Schaltet Device aus |
| `check_health()` | GET auf `/json/info` |

### scene_playback.py

| Feature | Beschreibung |
|---------|-------------|
| Solid-Black Pre-Entry | Sendet `{"transition":0, "seg":{"fx":0, "col":[[0,0,0]]}}` + 300ms Wartezeit vor dem ersten UDP-Frame. Eliminiert den Start-Flash. |
| `_playback_loop()` | Iteriert Frames und sendet per UDP DNRGB oder JSON API |
| Playback-Ende | Einfaches `turn_off()` → `{"on":false}`. Realtime-Timeout läuft natürlich ab. |
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
