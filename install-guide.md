# Pi OLED MP3 Player — Installation Guide

E.g. Install the MP3 player software on a Raspberry Pi Zero W starting from a blank SD card.

---

## 1. Flash the OS

1. Download **Raspberry Pi OS Bullseye** (recommended) from [raspberrypi.com/software](https://www.raspberrypi.com/software/operating-systems/)
2. Flash to a microSD card using Raspberry Pi Imager, BalenaEtcher, or `dd`

### During flashing (in Raspberry Pi Imager)
Click the gear icon and pre-configure:

- **Set hostname:** `raspberrypi`
- **Enable SSH** — allow password login
- **Set username:** `your-user`
- **Set password:** *(choose one)*
- **Configure WiFi** — enter your network SSID and password (needed for initial setup; will be disabled later)

---

## 2. First Boot & Initial Setup

Insert the SD card into the Pi Zero W and power on. Give it a minute to boot.

### SSH in
```bash
ssh your-user@raspberrypi.local
```

### Update packages
```bash
sudo apt update && sudo apt upgrade -y
```

### Enable I2C (for the OLED display)
```bash
sudo raspi-config nonint do_i2c 0
```

Or via the menu:
```bash
sudo raspi-config
```
→ Interface Options → I2C → Enable

### Reboot
```bash
sudo reboot
```

---

## 3. Install Dependencies

After reboot, SSH back in and run:

```bash
# System packages
sudo apt install -y python3-pip python3-pil python3-gpiozero mplayer

# Python packages
sudo pip3 install mutagen
```

### Install the OLED driver (Adafruit_SSD1306)

```bash
cd ~
git clone https://github.com/adafruit/Adafruit_Python_SSD1306.git
cd Adafruit_Python_SSD1306
sudo python3 setup.py install
cd ..
rm -rf Adafruit_Python_SSD1306
```

*Note:* This library has a known issue on newer Python/Raspbian versions. If `setup.py` fails, install the legacy Pillow it requires:
```bash
sudo apt install -y python3-pil python3-numpy
```

---

## 4. Copy the Script

Transfer the MP3 player script onto the Pi. There are several ways:

### Option A — via SCP (if you have the file on another machine)
```bash
scp Pi_OLED_MP3_Player.py your-user@raspberrypi.local:/home/your-user/
```

### Option B — via USB stick
Copy the file from the repo at:
```
Pi_OLED-MP3-Player/Pi_OLED_MP3_Player.py
```

### Option C — create a new file and paste
```bash
nano /home/your-user/Pi_OLED_MP3_Player.py
```
Then paste in the script content.

---

## 5. Set Up the Service

Create the systemd service file:

```bash
sudo nano /lib/systemd/system/mp3play.service
```

With this content:

```ini
[Unit]
Description=MP3 Player

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/your-user/Pi_OLED_MP3_Player.py

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable mp3play.service
sudo systemctl start mp3play.service
```

Check it's running:

```bash
journalctl -u mp3play.service --no-pager -n 20
```

---

## 6. Hardware Setup

### GPIO Button Mapping (BCM pin numbers)

| Button   | GPIO | Header Pin | Function |
|----------|------|------------|----------|
| PLAY     | 12   | 32         | Stop / Play |
| NEXT     | 7    | 26         | Next track / Browse next |
| PREV     | 20   | 38         | Prev track / Browse prev |
| VOLDN    | 16   | 36         | Volume down |
| VOLUP    | 8    | 24         | Volume up |
| FAVMODE  | 25   | 22         | FAV add/remove / Rotate mode |

### OLED Display (SSD1306 128×32)

Connect to the I2C pins on the Pi Zero W's GPIO header:
- **VCC** → 3.3V or 5V (check your OLED specs)
- **GND** → Ground
- **SDA** → GPIO 2 (pin 3)
- **SCL** → GPIO 3 (pin 5)

### USB Audio Dongle

Plug the USB audio dongle into the **data-capable micro USB port** (the one on the side, not the one labelled for power).

---

## 7. Check It Works

Reboot and confirm the OLED displays the player version:

```bash
sudo reboot
```

After 30–60 seconds, the OLED should show: **MP3 Player: v1.90**

Then test the buttons — pressing PLAY should bring up the tracks display.

---

## 8. Boot Optimisation

The default boot takes ~55s, mostly waiting for WiFi DHCP (~30s). Since WiFi is toggled on-demand via the MP3 player buttons, we can skip that at boot.

### Disable unnecessary services

```bash
sudo systemctl disable dhcpcd.service
sudo systemctl disable hciuart.service bluetooth.service
```

### Grant the script permission to toggle WiFi and Bluetooth

```bash
echo 'your-user ALL=(root) NOPASSWD: /sbin/ip link set wlan0 up, /sbin/ip link set wlan0 down, /sbin/dhcpcd, /bin/systemctl start bluetooth.service, /bin/systemctl stop bluetooth.service, /bin/systemctl start hciuart.service, /bin/systemctl stop hciuart.service' | sudo tee /etc/sudoers.d/wifi-toggle
```

### Reboot and verify

```bash
sudo reboot
```

Check the boot time:

```bash
systemd-analyze time
systemd-analyze blame | head -10
```

Expected result: **~35s total** (down from ~55s).

---

## 9. Using the MP3 Player

### Music Directory Structure

Place MP3 files on the SD card at:
```
/home/your-user/Music/<Artist>/<Album>/<track>.mp3
```

Or on a USB stick at:
```
/media/your-user/<drive>/<Artist>/<Album>/<track>.mp3
```

The script loads tracks into these structures with paths parsed as:
```
Artist / Album / Song / ...
```

### System Menu

Press **VOLUP + VOLDN together** (when stopped) to open the system menu:

```
WiFi: ON  BT: OFF
PLAY = SHUTDOWN
NEXT = TOGGLE WiFi
FAV = TOGGLE BT
```

| Button | Action |
|--------|--------|
| PLAY   | Shutdown the Pi |
| NEXT   | Toggle WiFi on/off |
| FAVMODE | Toggle Bluetooth on/off |
| PREV   | Exit menu |

### Controls (while playing)

| Button | Push | Hold |
|--------|------|------|
| PLAY   | Stop | Play (if stopped) |
| NEXT   | Next track | Next album |
| PREV   | Previous track | Previous album |
| VOLDN  | Volume down | Volume down |
| VOLUP  | Volume up | Volume up |
| FAVMODE | FAV add/remove | Rotate play mode |

---

## 10. SSH After WiFi Toggle

When you toggle WiFi on via the system menu, the Pi gets an IP via DHCP. It may get a different address than before. Use mDNS to find it reliably:

```bash
ssh your-user@raspberrypi.local
```

---

## 11. Troubleshooting

### Script won't start — log file error
If running manually as `your-user` after the service has run as root:
```bash
sudo rm /home/your-user/mp3_player.log
```

### OLED stays blank
Check I2C is enabled:
```bash
ls /dev/i2c*
```
Should show at least `/dev/i2c-1`.

### No audio / distortion
- Check the USB audio dongle is plugged into the data USB port (not the power port)
- Try a different power supply — the Pi Zero W is sensitive to under-voltage

### WiFi toggle doesn't work
- Check the sudoers file is in place: `sudo cat /etc/sudoers.d/wifi-toggle`
- Confirm the `systemctl` path: `which systemctl` — update the sudoers entry if it's at a different path

### View service logs
```bash
journalctl -u mp3play.service --no-pager -n 50
```

---

## Appendix: Full File Listing

| File | Path | Purpose |
|------|------|---------|
| `Pi_OLED_MP3_Player.py` | `/home/your-user/` | Main script |
| `mp3play.service` | `/lib/systemd/system/` | Systemd service |
| `wifi-toggle` | `/etc/sudoers.d/` | Sudo permissions |
| `mp3_player.log` | `/home/your-user/` | Debug log |
| `OLEDconfig.txt` | `/home/your-user/` | Player settings |
| `favourites.txt` | `/home/your-user/` | Favourite track numbers |
| `tracks.txt` | `/home/your-user/` | Track index (generated) |
| `radio_stns.txt` | `/home/your-user/` | Custom radio stations (optional) |