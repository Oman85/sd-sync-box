#!/bin/bash
# Install SD Sync Box on Debian / Ubuntu (64-bit PC) or Raspberry Pi OS (64-bit).
# Run: sudo ./install.sh              renames the computer to "sdsync" so http://sdsync.local works
#      sudo ./install.sh --screen     also shows the progress screen full-screen on the attached monitor
#      sudo ./install.sh --keep-hostname
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run with sudo: sudo ./install.sh"; exit 1; }
command -v apt-get >/dev/null || { echo "This installer needs Debian, Ubuntu or Raspberry Pi OS."; exit 1; }

KEEP_HOSTNAME=0
SCREEN=0
for arg in "$@"; do
  case "$arg" in
    --keep-hostname) KEEP_HOSTNAME=1 ;;
    --screen) SCREEN=1 ;;
    *) echo "Unknown option $arg"; exit 1 ;;
  esac
done

ARCH=$(uname -m)
case "$ARCH" in
  x86_64|aarch64) ;;
  *)
    echo "Warning: this is $ARCH. YouTube downloads need the Deno JavaScript runtime,"
    echo "which only runs on 64-bit systems (x86_64 PCs, Pi Zero 2 W / Pi 3/4/5 with 64-bit OS)."
    echo "Downloads will likely fail. Continuing anyway in 10 seconds (Ctrl+C to stop)."
    sleep 10
    ;;
esac

SRC=$(cd "$(dirname "$0")" && pwd)
apt-get update
apt-get install -y python3-venv python3-pip ffmpeg dosfstools avahi-daemon curl

mkdir -p /opt/sdsync /var/lib/sdsync /mnt/sdsync
rm -rf /opt/sdsync/sdsync
cp -r "$SRC/sdsync" /opt/sdsync/
[ -d /opt/sdsync/venv ] || python3 -m venv /opt/sdsync/venv
/opt/sdsync/venv/bin/pip install -U pip
/opt/sdsync/venv/bin/pip install -U "yt-dlp[default,deno]"

# The 512 MB Pi Zero 2 W needs some swap while ffmpeg runs (a PC with 4 GB does not).
if [ -f /etc/dphys-swapfile ] && [ "$(awk '/MemTotal/ {print $2}' /proc/meminfo)" -lt 1000000 ]; then
  sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
  systemctl restart dphys-swapfile || true
fi

if [ "$KEEP_HOSTNAME" = 0 ]; then
  hostnamectl set-hostname sdsync || true
  if grep -q '^127.0.1.1' /etc/hosts; then
    sed -i 's/^127.0.1.1.*/127.0.1.1\tsdsync/' /etc/hosts
  else
    echo -e "127.0.1.1\tsdsync" >> /etc/hosts
  fi
  systemctl restart avahi-daemon || true
fi
NAME=$(hostname)

if ss -ltn 2>/dev/null | grep -q ':80 '; then
  echo "Note: something else already uses port 80. Edit /etc/systemd/system/sdsync.service"
  echo "to add --port 8080 after 'python -m sdsync', then: sudo systemctl daemon-reload && sudo systemctl restart sdsync"
fi
cp "$SRC/systemd/sdsync.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now sdsync

if [ "$SCREEN" = 1 ]; then
  # A tiny kiosk: the "cage" compositor runs one full-screen Chromium on the monitor, no desktop needed.
  if ! apt-cache policy chromium | grep -q 'Candidate: [0-9]'; then
    echo "Chromium isn't available as a normal package here (Ubuntu ships it as a snap)."
    echo "The big screen needs Debian 12/13 or Raspberry Pi OS. Skipping it."
  else
    apt-get install -y cage chromium curl fonts-dejavu-core
    # Monitor standby when idle. Without wlopm the screen just goes black instead.
    apt-get install -y wlopm || echo "wlopm not available; the idle screen will black out instead of switching off."
    id sdsync-screen >/dev/null 2>&1 || useradd -m -s /usr/sbin/nologin sdsync-screen
    usermod -aG video,render,input sdsync-screen 2>/dev/null || usermod -aG video,input sdsync-screen
    cp "$SRC/systemd/sdsync-screen.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl disable --now getty@tty1.service || true
    systemctl enable --now sdsync-screen
    echo "Big screen is on. To turn it off: sudo systemctl disable --now sdsync-screen && sudo systemctl enable --now getty@tty1"
  fi
fi
echo
IP=$(hostname -I | awk '{print $1}')
echo "Done. Open http://$NAME.local (or http://$IP) on your phone or computer, same network."
