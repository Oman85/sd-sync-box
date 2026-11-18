# SD Sync Box

A small always-on computer at home that keeps your YouTube playlists downloaded
as MP3s and writes them to your car drives as soon as you plug them in:

- the **SD card for the Audi RNS-E**, in a USB card reader, and
- the **USB stick for a CD changer emulator**.

Each drive has its own list of folders, and you choose which playlists go into each
folder. A monitor on the VGA port can show a full-screen progress display, and the
web page (on your phone) tells you when a drive is done and safe to pull.

It runs on either:
- **a PC such as a Lenovo ThinkCentre M600** (any 64-bit x86 PC with 2 GB+ RAM), or
- **a Raspberry Pi Zero 2 W** (see the Pi section at the end).

## What you need (PC)

| Part | Notes |
|---|---|
| ThinkCentre M600 (or any 64-bit PC) | 4 GB RAM is plenty. Needs Wi-Fi or an Ethernet cable to your router. |
| Space on its drive | The box keeps an MP3 copy of every playlist, roughly the size of your car card (up to 32 GB). |
| USB card reader for full-size SD cards | Any simple USB reader. Plug it into a USB port and leave it there. |
| SD card for the car | SDHC, **32 GB or smaller**, formatted **FAT32**. |
| USB stick for the CD changer emulator | FAT32. Check your emulator's manual for its size limit (often 32 GB). |
| Monitor on the VGA port (optional) | For the full-screen progress display. A touch monitor (e.g. ELO, USB touch) lets you control the box from it. |

The box only ever writes to a card in a **USB reader** (or a built-in SD slot). It skips
the drive the system runs from, so it can't write to the PC's own disk by mistake.

## Set up the PC (about 30 minutes)

1. **Install Linux.** On another computer, download **Debian 13 netinst (amd64)** from debian.org,
   or **Ubuntu Server 24.04 LTS**, and write it to a USB stick with *balenaEtcher* or *Rufus*.
   Boot the M600 from the stick (press **F12** at the Lenovo logo for the boot menu) and install.
   During the Debian install:
   - Set the hostname to `sdsync`.
   - On the *Software selection* screen, untick the desktop and tick **SSH server**.
     (A desktop works too, it just isn't needed.)
   - Connect to your Wi-Fi when asked, or use an Ethernet cable.
2. **Copy this folder over and install.** Log in on the M600 (or from your computer with
   `ssh youruser@sdsync.local`), then:
   ```
   # copy the zip onto a USB stick, or from your computer:  scp sd-sync-box.zip youruser@sdsync.local:
   sudo apt install -y unzip
   unzip sd-sync-box.zip
   cd sd-sync-box && sudo ./install.sh --screen
   ```
   `--screen` turns on the full-screen progress display on the VGA monitor (Debian only;
   leave it out if no monitor is attached). The installer renames the computer to `sdsync`;
   add `--keep-hostname` if you don't want that.
3. Open **http://sdsync.local** on your phone or computer on the same network. If that name does
   not work (some Android phones), use the IP address the installer prints.
4. Optional, so it survives power cuts: in the M600's BIOS (F1 at boot), set
   *Power > After Power Loss* to **Power On**.

## Using it

### Playlists
Paste a YouTube playlist link under **Add playlist** and pick which drive it goes on.
Downloads start straight away, then the box checks for new songs every 6 hours (changeable).
Playlists must be *Public* or *Unlisted*. Each playlist is downloaded once, however many
drives use it. *Pause* stops a playlist from downloading or being written; *Delete* removes it everywhere.

### Drives and folders
There are two drive sections, **RNS-E SD card** and **CD changer USB**. Each has a list of
folders, and each folder takes its songs from **one or more playlists**, played one after the other:

- *Add folder* creates a folder with a playlist; *Add to folder* adds another playlist to it.
  The **x** on a playlist takes it back out.
- On the SD card folders are numbered by their position (`01 Road Trip`, `02 ...`); *Up* and
  *Down* change the order. Moving or renaming a folder means it gets copied again.
- On the CD changer stick folder names are used exactly as typed. New folders are named
  `CD01`, `CD02` ... automatically, which is what most changer emulators expect.
- Each drive has its own limits: max songs per folder, max folders, and whether a playlist that's
  too long is **split** into `Name (1)`, `Name (2)` or the rest is **left out**. The SD card defaults
  to 250 songs and 99 folders, split. The changer defaults to 99 songs and 6 folders, left out
  (six "CDs" like a real changer).

### Plugging in a drive
- **The first time** you plug in a card or stick, the page shows *Unknown drive* with a button for
  each kind (*This is the RNS-E SD card* / *This is the CD changer USB*). That sets the drive's
  volume label (`RNSE` or `CDCHANGER`) and changes no files. After that the box recognises it
  by itself. A drive it doesn't recognise is never written to.
- Both drives can be plugged in at once; they're written at the same time.
- The page and the big screen show a progress bar and then **SAFE TO REMOVE**. You can leave a
  drive plugged in; it updates after each download.
- **Rewrite whole drive** erases this box's folders on that drive and writes them again in order.
  Use it if the car plays songs out of order.

### The look
Two looks, switched under **Settings > Look**:
- **Cyberspace** (default): neon magenta, cyan and yellow on black like the computer screens in
  90s hacker films, with an animated background behind the monitor view. Pick it under
  *Settings > Monitor background*:
  - **Gibson: towers of data** (default), a slow glide down an avenue of tall see-through towers
    with data scrolling up their faces, like the supercomputer in the film. Open
    `http://sdsync.local/screen?bgonly` to see it without the windows.
  - **3D falling code**, in the style of xscreensaver's *GLMatrix* hack by Jamie Zawinski
    (redrawn from scratch for the browser; it doesn't need xscreensaver installed)
  - **Data city fly-through**, glowing towers of data
  - **None**
- **Classic 90s desktop**: grey bevelled windows and navy title bars on a black desktop.

Both have the same buttons, touch keyboard and message boxes.

### The monitor (touch screen)
With `--screen`, the monitor shows a full-screen window view: the YouTube download (current song,
playlist N of M), a progress bar for each plugged-in drive, the activity log, and a taskbar with
big buttons: *Check YouTube now*, *Write drives now* and *Playlists & drives...*.

It's made for a touch monitor such as an ELO:
- Every button is finger-sized, and *Unknown drive* can be answered right on the screen.
- *Playlists & drives...* opens the full control page. Text fields there bring up an on-screen
  keyboard, with a **YT link** key that types `https://www.youtube.com/playlist?list=` for you.
  Pasting a link from your phone is still quicker for long links.
- After 3 minutes without a touch it goes back to the monitor view.
- **The monitor switches itself off** after 5 minutes without a touch (change it, or pick *Never*,
  under *Settings*). It comes back on when you **touch it**, **plug in or pull out a drive**, or a
  drive finishes writing. It stays on while a drive is being written. The first touch on a sleeping
  screen only wakes it, so you can't press a button by accident. The monitor goes into standby
  like a PC screen saver; if your setup can't do that, the screen goes black instead.
- Questions like "Delete this playlist?" appear as Yes/No message boxes.

**ELO touch:** USB ELO monitors work as a normal touchscreen with no driver. Plug in its USB cable
as well as the VGA cable. If touches land in the wrong place, or your ELO only has a serial (RS-232)
touch cable, see "When things go wrong" below.

You can also open the same view in any browser at `http://sdsync.local/screen`. To turn the
monitor view off:
`sudo systemctl disable --now sdsync-screen && sudo systemctl enable --now getty@tty1`.

### Cache and automatic checks
- **Cache:** every song is kept on the box's own drive, so a card or stick is written in minutes
  without waiting for YouTube, even with the internet down. Each song is downloaded only once, even
  if several drives or folders use it. The status bar and the monitor show how many songs are
  cached, how much space they use and how much is free. A song removed from a YouTube playlist is
  removed from the cache, and from your drives on the next write.
- **YouTube check** every 6 hours (changeable), right after you add a playlist, and **when you plug
  in a drive** if the last check was over an hour ago. A drive is written from the cache straight
  away, and any new songs are added when the check finishes.
- **Daily health check:** opens every cached MP3 and deletes any broken one, so it downloads again.
  It also clears half-finished downloads and warns in the log when the box has less than 2 GB free.
- **Before every write,** the songs already on the drive are checked against the cache (size), and a
  damaged or half-written folder is rewritten in order.
- **yt-dlp** (the YouTube downloader) updates itself once a day, because YouTube changes often.

## How the drives are laid out

```
SD card (RNS-E)                         USB stick (CD changer)
/01 Road Trip/001 Artist - Song.mp3     /CD01/001 Artist - Song.mp3
/01 Road Trip/002 Artist - Song.mp3     /CD01/002 ...
/02 Summer (1)/001 ...                  /CD02/001 ...
/02 Summer (2)/251 ...
/sdsync.json   the box's record of what it wrote (on both)
```

Choices made for the RNS-E and changer emulators, all of them conservative:

- MP3, constant bitrate 192 kbps, 44.1 kHz, stereo. No variable bitrate.
- ID3v2.3 plus ID3v1 tags (title, artist, album = playlist name), **no cover art**,
  since large embedded pictures make some older units skip tracks or load slowly.
- Plain ASCII names (ü becomes u, emoji removed), at most 60 characters,
  "(Official Video)" and similar stripped, "Artist - Song" split into tags.
- One folder level.
- Many older head units and changer emulators play in the order files were *written*, not by
  name. So the box only ever adds songs to the end of a folder; if a playlist is reordered or a
  song is removed, that folder is rewritten from scratch in the right order.
- Files and folders it did not create are never touched.

I couldn't confirm the exact folder and file limits of the 193PU firmware or your changer
emulator, so the limits are settings on each drive.

## Formatting a car card or stick

Both need FAT32. Use the official *SD Card Formatter* app on Windows/Mac, or on the box with the card in the reader:
```
lsblk -o NAME,SIZE,TRAN,MOUNTPOINT    # the card is the one with TRAN "usb" and the card's size
sudo mkfs.vfat -F 32 -n RNSE /dev/sdX1        # or -n CDCHANGER for the changer stick
```
On the M600 the PC's own drive is usually `sda` too, so check the size and `usb` column
carefully before formatting.
This erases the drive. Formatting with those labels means the box recognises it right away.
A drive formatted as exFAT or NTFS (most 64 GB+ cards and sticks) is refused with a message on the page.

## When things go wrong

- **"Sign in to confirm you're not a bot"** in the log: YouTube is rate-limiting your home
  connection. Wait a day, or export YouTube cookies from your browser to a `cookies.txt` file,
  copy it to the box and set `"cookies_file": "/var/lib/sdsync/cookies.txt"` in
  `/var/lib/sdsync/config.json`, then `sudo systemctl restart sdsync`.
- **Downloads stopped working:** the box updates yt-dlp once a day by itself. To force it:
  `sudo /opt/sdsync/venv/bin/pip install -U "yt-dlp[default,deno]" && sudo systemctl restart sdsync`.
- **Logs:** `journalctl -u sdsync -f` (and `journalctl -u sdsync-screen` for the monitor).
- **Touch does nothing:** run `sudo libinput list-devices | grep -i -A3 elo`. If it isn't listed and
  your ELO has a serial touch cable, it needs `inputattach` (`sudo apt install inputattach`, then
  `sudo inputattach --elo /dev/ttyS0 --daemon`), or a USB touch controller.
- **Touches land in the wrong place:** usually a second display output is active. Unplug other
  monitors, then `sudo systemctl restart sdsync-screen`.
- **Monitor stays black:** check `systemctl status sdsync-screen`. If you moved the web page off
  port 80, change `:80` in `/etc/systemd/system/sdsync-screen.service` to match.
- **Songs that fail** (deleted, region-blocked) are retried once a week.

## Running it on a Raspberry Pi Zero 2 W instead

Same software, same installer. You need a **Pi Zero 2 W** (the original Zero / Zero W can't
run the JavaScript runtime YouTube now requires), a 64 GB microSD for the Pi, a micro-USB OTG
adapter for the card reader (port marked **USB**, not **PWR**) and a 5 V 2.5 A power supply.
Flash **Raspberry Pi OS Lite (64-bit)** with Raspberry Pi Imager, setting hostname `sdsync`,
SSH and your Wi-Fi in its settings, then copy the folder over and run `sudo ./install.sh`.

## Files

- `sdsync/downloader.py`: playlist listing, download, MP3 conversion and tagging
- `sdsync/cardsync.py`: drive layout per target, space check, append-only writing
- `sdsync/card.py`: finds cards and sticks on USB (never the system disk), mounts, unmounts, labels
- `sdsync/service.py`: background loops, status, health check, Pi LED
- `sdsync/display.py`: monitor standby and wake
- `sdsync/web.py`: the web page and the `/screen` display
- `sdsync/theme.py`: both looks, the data-city animation, message boxes and on-screen keyboard
- `systemd/sdsync-screen.service`: full-screen kiosk for the monitor
- `tests/`: run `python3 -m pytest tests` (no hardware needed)

Only download music you have the right to; YouTube's terms don't allow downloading most content.
