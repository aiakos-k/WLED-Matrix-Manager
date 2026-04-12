# Home Assistant Add-on: WLED Matrix Manager

Create and manage pixel-art scenes for WLED LED matrices.

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

## About This Add-on

WLED Matrix Manager lets you create, manage, and play pixel-art scenes for WLED-controlled
LED matrices directly from Home Assistant.

![Scenes](../images/screenshot-scenes.png)

### Features

- **Scene Editor** — Create pixel-art scenes with multiple frames
- **Device Management** — Add and configure WLED devices
- **Playback** — Play animations on WLED matrices (JSON API or UDP DNRGB)
- **HA Integration** — Scenes as Home Assistant entities, controllable via automations
- **Auto-Discovery** — Automatically discover WLED devices from Home Assistant
- **Import/Export** — Import and export scenes as binary files or images
- **Live Preview** — WebSocket-based real-time preview in the browser

### Supported WLED Protocols

| Protocol | Description |
|----------|-------------|
| JSON API | HTTP-based, for single frames and configuration |
| UDP DNRGB | Real-time streaming, ideal for animations (up to 489 LEDs/packet) |

## Support

If you find this project useful, consider buying me a coffee:

<a href="https://www.buymeacoffee.com/aiakosmk" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" alt="Buy Me a Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## License

EUPL-1.2 — See [LICENSE](https://eupl.eu/1.2/en/)

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
