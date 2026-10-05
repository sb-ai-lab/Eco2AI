import csv
import io
import os
import shutil

VENDOR_IDS = {
    0x10DE: "nvidia",
    0x1002: "amd",
    0x8086: "intel",
    0x19E5: "huawei",
}

VENDOR_ORDER = ("nvidia", "amd", "intel", "huawei", "google")


class Device:
    """One accelerator seen by the operating system, before a backend opens."""

    def __init__(self, vendor, name="", integrated=None):
        self.vendor = vendor
        self.name = name or ""
        self.integrated = integrated


def is_integrated_name(vendor, name):
    """
    True for an integrated GPU, False for a discrete accelerator, None if the
    name does not say which. NVIDIA, Ascend, and TPU are never integrated.
    """
    if vendor in ("nvidia", "huawei", "google"):
        return False
    text = (name or "").lower()
    if vendor == "intel":
        if not text:
            return None
        if any(token in text for token in ("arc", "flex", "data center gpu", "ponte vecchio", "battlemage")):
            return False
        return True
    if vendor == "amd":
        if not text:
            return None
        if any(token in text for token in ("instinct", "radeon pro", "radeon rx", "radeon vii", "firepro")):
            return False
        if "radeon graphics" in text or "radeon(tm) graphics" in text:
            return True
        return None
    return None


def rapl_package_present(root="/sys/class/powercap/intel-rapl"):
    """True when a top-level RAPL package energy file can be read."""
    if not root or not os.path.isdir(root):
        return False
    for entry in os.listdir(root):
        domain = os.path.join(root, entry)
        name_path = os.path.join(domain, "name")
        energy_path = os.path.join(domain, "energy_uj")
        if not os.path.isdir(domain) or not os.path.isfile(name_path):
            continue
        if not os.path.isfile(energy_path):
            continue
        try:
            with open(name_path, "r", encoding="utf-8") as handle:
                name = handle.read().strip()
        except OSError:
            continue
        if name.startswith("package"):
            return True
    return False


def eligible_vendors(devices, rapl_present):
    """
    Vendors to open. An integrated GPU is left out when RAPL package energy
    is already counted by the CPU tracker.
    """
    grouped = {}
    for device in devices:
        grouped.setdefault(device.vendor, []).append(device)
    chosen = {}
    for vendor in VENDOR_ORDER:
        group = grouped.get(vendor)
        if not group:
            continue
        if rapl_present and all(device.integrated is True for device in group):
            continue
        chosen[vendor] = group
    return chosen


def _class_is_accelerator(class_id):
    base = (class_id >> 16) & 0xFF
    return base in (0x03, 0x12)


def _read_hex(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return int(handle.read().strip(), 16)
    except (OSError, ValueError):
        return None


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _pci_devices(sysfs_root):
    devices = []
    if not sysfs_root or not os.path.isdir(sysfs_root):
        return devices
    for entry in sorted(os.listdir(sysfs_root)):
        folder = os.path.join(sysfs_root, entry)
        vendor_id = _read_hex(os.path.join(folder, "vendor"))
        class_id = _read_hex(os.path.join(folder, "class"))
        if vendor_id not in VENDOR_IDS or class_id is None:
            continue
        if not _class_is_accelerator(class_id):
            continue
        vendor = VENDOR_IDS[vendor_id]
        name = _read_text(os.path.join(folder, "name"))
        devices.append(Device(vendor, name, is_integrated_name(vendor, name)))
    return devices


def _windows_rows(runner):
    if runner is None:
        return []
    text = runner(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name,PNPDeviceID | ConvertTo-Csv -NoTypeInformation",
        ]
    )
    if not text:
        return []
    rows = []
    try:
        reader = csv.DictReader(io.StringIO(text))
    except csv.Error:
        return []
    for row in reader:
        if not row:
            continue
        name = row.get("Name") or row.get("name") or ""
        pnp = row.get("PNPDeviceID") or row.get("PnpDeviceId") or row.get("pnp") or ""
        rows.append((name, pnp))
    return rows


def _devices_from_pnp(rows):
    devices = []
    for name, pnp in rows:
        text = (pnp or "").upper()
        vendor = None
        for vid, label in VENDOR_IDS.items():
            if "VEN_%04X" % vid in text:
                vendor = label
                break
        if vendor is None:
            lowered = (name or "").lower()
            if "nvidia" in lowered:
                vendor = "nvidia"
            elif "radeon" in lowered or "amd" in lowered:
                vendor = "amd"
            elif "intel" in lowered or "arc" in lowered:
                vendor = "intel"
        if vendor is None:
            continue
        devices.append(Device(vendor, name, is_integrated_name(vendor, name)))
    return devices


def _add_if_missing(devices, vendor, present, name=""):
    if not present:
        return
    if any(device.vendor == vendor for device in devices):
        return
    devices.append(Device(vendor, name, is_integrated_name(vendor, name)))


def probe_devices(
    sysfs_root="/sys/bus/pci/devices",
    platform_name=None,
    windows_rows=None,
    which=None,
    exists=None,
    environ=None,
    command_runner=None,
):
    """
    Accelerators visible without loading a vendor Python package.
    sysfs covers Linux PCI devices. Windows uses Win32_VideoController.
    Driver CLIs and device nodes cover Ascend and TPU, which are not VGA.
    """
    if which is None:
        which = shutil.which
    if exists is None:
        exists = os.path.exists
    if environ is None:
        environ = os.environ
    if platform_name is None:
        platform_name = os.name

    devices = _pci_devices(sysfs_root)
    if windows_rows is None and platform_name == "nt" and not devices:
        windows_rows = _windows_rows(command_runner)
    if windows_rows:
        devices.extend(_devices_from_pnp(windows_rows))

    _add_if_missing(devices, "nvidia", bool(which("nvidia-smi")))
    _add_if_missing(devices, "amd", bool(which("rocm-smi") or which("amd-smi")))
    _add_if_missing(devices, "intel", bool(which("xpu-smi")))
    _add_if_missing(
        devices,
        "huawei",
        bool(which("npu-smi") or exists("/dev/davinci0") or exists("/dev/davinci_manager")),
        "Ascend",
    )
    tpu_env = environ.get("TPU_ACCELERATOR_TYPE") or environ.get("TPU_NAME")
    _add_if_missing(
        devices,
        "google",
        bool(which("tpu-info") or exists("/dev/accel0") or tpu_env),
        "TPU",
    )
    return devices
