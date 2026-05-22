# Moonraker-Yumi — Yumi Lab App for Klipper

Moonraker plugin that connects Klipper-based 3D printers to the [Yumi Lab](https://app.yumi-lab.com) platform.

## Features

- AI-powered print failure detection
- 25 FPS WebRTC webcam streaming (via Janus Gateway)
- Remote monitoring and control
- Mobile app support (iOS / Android)
- TURN relay via `app.yumi-lab.com`

## Supported Platforms

| Platform | OS | Architecture |
|----------|-----|-------------|
| SmartPi ONE (YumiOS V2) | Debian 13 Trixie | armhf |
| SmartPi ONE (YumiOS V2) | Debian 12 Bookworm | armhf |

> For legacy SmartPad V1, see [moonraker-yumi-lab](https://github.com/Yumi-Lab/moonraker-yumi-lab).

## Installation

```bash
cd ~
git clone https://github.com/Yumi-Lab/moonraker-app-yumi-lab.git
cd moonraker-app-yumi-lab
chmod +x install.sh
./install.sh -S "https://app.yumi-lab.com"
```

The installer will:
- Create a Python virtualenv (`moonraker-yumi-env`)
- Install Janus WebRTC Gateway (apt on Bookworm, pre-built .deb on Trixie)
- Create the `moonraker-yumi` systemd service
- Generate `moonraker-yumi-update.cfg` for Moonraker update manager

## Uninstall

```bash
sudo systemctl stop moonraker-yumi.service
sudo systemctl disable moonraker-yumi.service
sudo rm /etc/systemd/system/moonraker-yumi.service
sudo systemctl daemon-reload
rm -rf ~/moonraker-app-yumi-lab
rm -rf ~/moonraker-yumi-env
```

## Update Manager

The service auto-updates via Moonraker. Config in `moonraker-yumi-update.cfg`:

```ini
[update_manager moonraker-yumi]
type: git_repo
path: ~/moonraker-app-yumi-lab
origin: https://github.com/Yumi-Lab/moonraker-app-yumi-lab.git
is_system_service: False
managed_services: klipper
```

## Links

- [Yumi Lab Wiki](https://wiki.yumi-lab.com)
- [Yumi Lab App](https://app.yumi-lab.com)
- [Discord](https://discord.yumi-lab.com)

## Credits

Based on [Obico for Klipper](https://github.com/TheSpaghettiDetective/moonraker-obico) by TheSpaghettiDetective.
