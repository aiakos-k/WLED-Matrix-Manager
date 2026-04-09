# WLED Protocol Reference

This document describes the two communication protocols we use with WLED devices,
based on the [WLED firmware source code](https://github.com/wled/WLED/blob/main/wled00/udp.cpp)
and the official documentation.

---

## 1. JSON API (HTTP)

**Endpoint:** `POST http://<IP>/json/state`
**Docs:** https://kno.wled.ge/interfaces/json-api/

### How We Use It

We send JSON objects to control LEDs via Per-Segment Individual LED Control (`seg.i`).
This is the "safe" method — no flash, supports transitions, full control.

### Our Command Format

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

### Important State Properties

| Property | Type | Description |
|----------|------|-------------|
| `on` | bool | On/Off. `"t"` to toggle |
| `bri` | 0-255 | Master brightness. **When `on: false`, contains the last brightness** |
| `transition` | 0-65535 | Crossfade duration in 100ms units. `0` = instant |
| `tt` | 0-65535 | One-time transition only for this API call |
| `live` | bool | **Forces realtime mode and blanks LEDs.** No timeout! Must be ended with `{"live":false}` |
| `lor` | 0/1/2 | Live data override. 0=off, 1=until live ends, 2=until reboot |
| `seg.i` | array | Individual LED array. Format: `[index, [R,G,B], ...]` or ranges `[start, stop, [R,G,B]]` |

### Segment LEDs (`seg.i`) Format

Three variants:

```json
// Individual LEDs
{"seg":{"i":["FF0000","00FF00","0000FF"]}}

// With explicit index
{"seg":{"i":[0,"FF0000", 2,"00FF00", 4,"0000FF"]}}

// Ranges (start to stop-1)
{"seg":{"i":[0, 8, "FF0000", 10, 18, "0000FF"]}}
```

**Note:** LED indices are segment-based (LED 0 = first LED of the segment).

### Brightness Interaction

> "For your colors to apply correctly, make sure the desired brightness is set beforehand.
> Turning on the LEDs from an off state and setting individual LEDs in the same JSON request will not work!"

→ That's why we set `"on": true, "bri": X` in the same command along with `seg.i`.

---

## 2. UDP Realtime — DNRGB Protocol

**Port:** 21324 (default WLED UDP port)
**Docs:** https://kno.wled.ge/interfaces/udp-realtime/

### Protocol Types on Port 21324

| Byte 0 | Protocol | Max LEDs |
|--------|----------|----------|
| 0 | WLED Notifier (Sync) | - |
| 1 | WARLS | 255 |
| 2 | DRGB | 490 |
| 3 | DRGBW | 367 |
| **4** | **DNRGB** ← we use this | **489/packet** |
| 5 | DNRGBW | - |

### DNRGB Packet Format

```
Byte 0:    4 (protocol ID for DNRGB)
Byte 1:    Timeout in seconds (1-254, 255 = no timeout / indefinite)
Byte 2:    Start LED index high byte
Byte 3:    Start LED index low byte
Byte 4+:   [R, G, B, R, G, B, ...] pixel data from start index
```

**Max packet size:** 1472 bytes (UDP_IN_MAXSIZE in WLED)
→ Header: 4 bytes + 3 bytes/LED = max **489 LEDs per packet**
→ We use 458 LEDs/packet (`MAX_LEDS_PER_PACKET`) as a safety buffer

### Timeout Byte (Byte 1)

- `1-254`: Seconds until WLED automatically exits realtime mode
- `255`: No timeout — stays in realtime until explicitly ended
- `0`: **Special value — exits realtime immediately!**

From the source code:
```cpp
if (udpIn[1] == 0) {
    realtimeTimeout = 0;  // cancel realtime mode immediately
    return;
} else {
    realtimeLock(udpIn[1]*1000 + 1, REALTIME_MODE_UDP);
}
```

### Chunked Packets for Large Matrices

DNRGB supports any number of LEDs via multiple packets with different start indices:

```
Paket 1: [4, timeout, 0x00, 0x00, R,G,B, R,G,B, ...]  ← LEDs 0-457
Paket 2: [4, timeout, 0x01, 0xCA, R,G,B, R,G,B, ...]  ← LEDs 458-915
...
```

### WLED Processing (from udp.cpp)

```cpp
if (udpIn[0] == 4 && packetSize > 7) { // DNRGB
    unsigned id = ((udpIn[3] << 0) & 0xFF) + ((udpIn[2] << 8) & 0xFF00);
    for (size_t i = 4; i < packetSize - 2 && id < totalLen; i += 3, id++) {
        setRealtimePixel(id, udpIn[i], udpIn[i+1], udpIn[i+2], 0);
    }
}
// After all protocols:
if (useMainSegmentOnly) strip.trigger();
else                    strip.show();
```

→ Pixels are set **after realtimeLock()** and then displayed via `strip.show()`.

---

## 3. Realtime-Mode Lifecycle (Flash Cause & Solution)

### Entry: `realtimeLock()` — Cause of the Flash

```cpp
void realtimeLock(uint32_t timeoutMs, byte md) {
    if (!realtimeMode && !realtimeOverride) {
        // ── This block only runs on FIRST entry ──
        if (useMainSegmentOnly) {
            mainseg.clear();
            mainseg.freeze = true;
        } else {
            strip.fill(BLACK);   // All LEDs black
        }
        if (briT == 0) {
            // Strip was OFF → restore last brightness
            strip.setBrightness(briLast, true);
        }
    }
    realtimeMode = md;
    if (arlsForceMaxBri) strip.setBrightness(255, true);
    // show() only for GENERIC (JSON API), NOT for UDP!
    if (briT > 0 && md == REALTIME_MODE_GENERIC) strip.show();
}
```

### Why the Flash Occurs

1. WLED is currently displaying an effect (e.g., Rainbow) at brightness X
2. First UDP packet arrives → `realtimeLock()` is called
3. `strip.fill(BLACK)` fills the buffer with black
4. **BUT:** Between fill(BLACK) and the actual setRealtimePixel() + show(),
   the WLED effect loop can still render one frame → **flash of the old effect**
5. Additionally: `setBrightness(briLast)` restores brightness if the strip was OFF
6. `arlsForceMaxBri` in WLED settings can force brightness to 255

### Exit: `exitRealtime()`

```cpp
void exitRealtime() {
    strip.setBrightness(bri, true);  // Restore normal brightness
    realtimeTimeout = 0;
    realtimeMode = REALTIME_MODE_INACTIVE;
    strip.show();  // Displays the normal effect again
}
```

→ Called automatically when the timeout expires.

### Solution: "Solid Black Effect" Before UDP Start ✅

After many iterations (10+), the following strategy proved to be the only reliable solution:

**Before the first UDP frame:**
```json
{"transition": 0, "seg": {"fx": 0, "col": [[0, 0, 0]]}}
```

Then **wait 300ms** before sending the first UDP packet.

#### Why This Works

1. The effect is set to **Solid (fx:0)** with color **black**
2. `transition: 0` → instant, no crossfade
3. WLED renders black pixels within a few effect cycles (33ms at 30fps)
4. 300ms wait gives WS2812B enough time for 2+ full `show()` cycles
   (4096 LEDs × 30µs/LED = ~123ms per show)
5. When the first UDP packet triggers `realtimeLock()` and the effect loop renders
   one last frame → it's **solid black** → no visible flash

#### What Did NOT Work (and Why)

| Attempt | Problem |
|---------|---------|
| `{"live": true}` before UDP | Sets realtime without timeout. `turn_off()` at the end is ignored (device stays in realtime). `{"live":false}` causes end-flash via `exitRealtime()`. |
| `{"on":true, "bri":255, "live":true}` atomic | WLED processes `on`+`bri` BEFORE `live` in `deserializeState()` → effect renders one frame at full brightness → flash is even stronger |
| `{"on":false}` → UDP → `{"on":true}` | UDP on a turned-off device still triggers `realtimeLock()` with `setBrightness(briLast)`. The `on:true` afterwards triggers `colorUpdated()` → old effect flashes briefly |
| Multiple black UDP pre-frames | Flash happens on the FIRST UDP packet in `realtimeLock()`. Additional frames come too late — the effect loop has already rendered |
| `{"on":true, "bri":255, "seg":{"fx":0, "col":[[0,0,0]]}}` | `on`+`bri` are processed BEFORE `seg`. For one frame WLED renders the old effect at the new brightness |

#### Why ONLY `seg` Changes Work

WLED's `deserializeState()` processes properties in this order:
1. `on`, `bri` → State changes, trigger `colorUpdated()` → effect renders
2. `transition` → Transition time
3. `seg` → Segment properties (effect, color, etc.)

If you omit `on`/`bri` and ONLY change `seg`, no state change is triggered
that renders the old effect. The effect switches directly to Solid Black.

### Playback End: Simple `turn_off()` ✅

```json
{"on": false}
```

At the end of scene playback, a simple `turn_off()` is sufficient. The UDP realtime timeout
(typically 5 seconds) expires naturally. `exitRealtime()` then calls `setBrightness(bri)`
and `show()` — but since the device is already OFF (`bri=0`), `show()` displays nothing.

**No `send_udp_cancel()` or `{"live":false}` needed** — both trigger `exitRealtime()`
immediately, which can briefly display the stored effect before `turn_off()` takes effect.

### WLED Settings That Affect Realtime

In WLED under Settings → Sync:

| Setting | Description |
|---------|-------------|
| **Force Max Brightness** (`arlsForceMaxBri`) | Forces brightness 255 in realtime mode |
| **Realtime Timeout** (`realtimeTimeoutMs`) | Default timeout for realtime (overridden by `live:true`) |
| **Use Main Segment Only** | Use only the main segment for realtime (freeze instead of fill) |

---

## 4. Our Implementation

### device_controller.py

| Method | Description |
|--------|-------------|
| `send_json_command()` | HTTP POST to `/json/state` via aiohttp |
| `generate_wled_command()` | Builds JSON with `seg.i` from pixel data (range compression) |
| `send_udp_dnrgb()` | Sends DNRGB packets with chunking (458 LEDs/packet) |
| `send_udp_cancel()` | Sends `[4,0,0,0]` — DNRGB with timeout=0 to end realtime immediately |
| `turn_off()` | `{"on": false}` — Turns device off |
| `check_health()` | GET on `/json/info` |

### scene_playback.py

| Feature | Description |
|---------|-------------|
| Solid-Black Pre-Entry | Sends `{"transition":0, "seg":{"fx":0, "col":[[0,0,0]]}}` + 300ms wait before the first UDP frame. Eliminates the start flash. |
| `_playback_loop()` | Iterates frames and sends via UDP DNRGB or JSON API |
| Playback End | Simple `turn_off()` → `{"on":false}`. Realtime timeout expires naturally. |
| Upscaling | `upscale_pixel_data()` scales scene resolution to device resolution |
| Device Exclusivity | Only one scene per device IP at a time |

### Brightness Chain

```
Frame Brightness (0-255)
    ↓
    ├─ JSON API: "bri" property (WLED master brightness)
    │   → WLED applies it globally to all seg.i pixels
    │
    └─ UDP DNRGB: Brightness applied in software to pixel values
        → No separate brightness byte in the DNRGB protocol
        → Pixel = [R*factor, G*factor, B*factor]
```

---

## 5. References

- **WLED Firmware Source:** https://github.com/wled/WLED/blob/main/wled00/udp.cpp
- **UDP Realtime Doku:** https://kno.wled.ge/interfaces/udp-realtime/
- **JSON API Doku:** https://kno.wled.ge/interfaces/json-api/
- **UDP Sync/Notifier:** https://kno.wled.ge/interfaces/udp-notifier/
