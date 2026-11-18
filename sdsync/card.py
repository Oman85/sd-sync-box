"""Find the SD card in the USB reader, mount it, unmount it.

Works on a Raspberry Pi or a normal PC. The reader is a USB disk (or a
built-in SD slot); the disk the system runs from is always skipped.
An empty reader shows up with size 0.
"""
import glob
import logging
import os
import subprocess

from . import config

log = logging.getLogger("sdsync.card")


def _blkid(dev, field):
    r = subprocess.run(["blkid", "-o", "value", "-s", field, dev], capture_output=True, text=True)
    return r.stdout.strip()


SYSTEM_MOUNTS = ("/", "/boot", "/boot/efi", "/boot/firmware", "/home", "/usr", "/var")


def _disk_of(name):
    """sda1 -> sda, mmcblk0p2 -> mmcblk0, dm-0 -> the disks under it."""
    path = os.path.realpath(f"/sys/class/block/{name}")
    if os.path.exists(os.path.join(path, "partition")):
        return {os.path.basename(os.path.dirname(path))}
    slaves = glob.glob(os.path.join(path, "slaves", "*"))
    if slaves:
        out = set()
        for sl in slaves:
            out |= _disk_of(os.path.basename(sl))
        return out
    return {name}


def system_disks():
    """Disks that hold the running system or swap. These are never touched."""
    names = set()
    try:
        with open("/proc/mounts") as f:
            for line in f:
                dev, where = line.split()[:2]
                if where in SYSTEM_MOUNTS and dev.startswith("/dev/"):
                    names.add(os.path.basename(os.path.realpath(dev)))
        with open("/proc/swaps") as f:
            for line in f.readlines()[1:]:
                dev = line.split()[0]
                if dev.startswith("/dev/"):
                    names.add(os.path.basename(os.path.realpath(dev)))
    except OSError:
        pass
    disks = set()
    for n in names:
        disks |= _disk_of(n)
    return disks


def _is_card_reader(sysdir):
    """A USB disk (USB card reader), or a built-in SD slot (mmcblk) that isn't the system disk."""
    disk = os.path.basename(sysdir)
    real = os.path.realpath(sysdir)
    return disk.startswith("mmcblk") or "/usb" in real


def _model(sysdir):
    parts = []
    for f in ("device/vendor", "device/model"):
        try:
            with open(os.path.join(sysdir, f)) as fh:
                parts.append(fh.read().strip())
        except OSError:
            pass
    return " ".join(p for p in parts if p) or "Drive"


def find_cards():
    """All plugged-in cards and USB sticks: [{dev, fstype, uuid, label, model}].

    Only USB disks (card reader, USB stick) and built-in SD slots are
    considered, and never a disk the system runs from, so the PC's own
    drive is safe.
    """
    skip = system_disks()
    found = []
    candidates = sorted(glob.glob("/sys/block/sd*")) + sorted(glob.glob("/sys/block/mmcblk*"))
    for sysdir in candidates:
        disk = os.path.basename(sysdir)
        if disk in skip or not _is_card_reader(sysdir):
            continue
        try:
            with open(os.path.join(sysdir, "size")) as f:
                if int(f.read().strip() or 0) == 0:
                    continue  # reader with no card in it
        except OSError:
            continue
        model = _model(sysdir)
        parts = sorted(os.path.basename(p) for p in glob.glob(os.path.join(sysdir, disk + "*")))
        entry = {"dev": "/dev/" + disk, "fstype": "", "uuid": "", "label": "", "model": model}
        for name in parts or [disk]:
            dev = "/dev/" + name
            fstype = _blkid(dev, "TYPE")
            if fstype:
                entry = {"dev": dev, "fstype": fstype, "uuid": _blkid(dev, "UUID"),
                         "label": _blkid(dev, "LABEL"), "model": model}
                break
        found.append(entry)
    return found


def find_card():
    cards = find_cards()
    return cards[0] if cards else None


def set_label(dev, label):
    """Set the FAT volume label (does not touch any files)."""
    if _mounted_at(dev):
        unmount(dev)
    subprocess.run(["fatlabel", dev, label], check=True, capture_output=True, text=True)


def _mounted_at(dev):
    with open("/proc/mounts") as f:
        for line in f:
            parts = line.split()
            if parts[0] == dev:
                return parts[1].replace("\\040", " ")
    return None


def mount(dev):
    where = _mounted_at(dev)
    if where:
        return where
    point = os.path.join(config.MOUNT_POINT, os.path.basename(dev))
    os.makedirs(point, exist_ok=True)
    subprocess.run(
        ["mount", "-t", "vfat", "-o", "noatime,flush,shortname=mixed", dev, point],
        check=True, capture_output=True, text=True,
    )
    return point


def unmount(dev):
    subprocess.run(["sync"], check=False)
    where = _mounted_at(dev)
    if where:
        subprocess.run(["umount", where], check=True, capture_output=True, text=True)


def capacity_gb(dev):
    try:
        with open(f"/sys/class/block/{os.path.basename(dev)}/size") as f:
            return int(f.read()) * 512 / 1e9
    except OSError:
        return 0.0
