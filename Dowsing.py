import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import zipfile

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except Exception:
    tk = None
    messagebox = None
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple


APP_NAME = "Dowsing"
MODE_NAME = "Default (For Precog)"
KEEP_OUTPUT_FOLDER_AFTER_ZIP = False  # False = only keep the .zip file if compression succeeds.
HIDE_CONSOLE_WHEN_GUI = True  # Hide the legacy console when the Tkinter UI is available.

# Prevent child console applications (PowerShell, cmd, DISM, powercfg, pnputil,
# wevtutil, etc.) from flashing a console window while the GUI is running.
SUBPROCESS_CREATIONFLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

OUTPUT_FILES = {
    "OS Version": "_OSVersion.txt",
    "SystemInfo": "_SystemInfo.txt",
    "Windows Version Reg": "_WindowsVersionReg.txt",
    "BCD Info": "_BCDInfo.txt",
    "DISM Driver Info": "_Dism_DriverInfo.txt",
    "PnP Devices Info": "_PnpDeviceInfo.txt",
    "PnP Devices CSV": "_PnpDeviceInfo.csv",
    "PnP Problem Devices": "_PnpProblemDevices.txt",
    "PnP Problem Devices CSV": "_PnpProblemDevices.csv",
    "Driver Query": "_DriverQuery.txt",
    "Driver Query CSV": "_DriverQuery.csv",
    "Windows Driver CSV": "_WindowsDriver.csv",
    "MSInfo32 Report": "_SysInfo.txt",
    "DXDiag Report": "_DxDiag.txt",
    "Catalog Map": "_CatalogMap.csv",
    "System Summary JSON": "_SystemSummary.json",
    "Hardware Inventory JSON": "_HardwareInventory.json",
    "SetupAPI Device Log": "_SetupAPI.dev.log",
    "PowerCfg Available Sleep States": "_PowerCfg_A.txt",
    "PowerCfg Requests": "_PowerCfg_Requests.txt",
    "PowerCfg LastWake": "_PowerCfg_LastWake.txt",
    "PowerCfg Wake Armed": "_PowerCfg_WakeArmed.txt",
    "SleepStudy Report": "_SleepStudy.html",
    "Energy Report": "_EnergyReport.html",
    "Installed Apps Win32 CSV": "_InstalledApps_Win32.csv",
    "Installed Apps Appx CSV": "_InstalledApps_Appx.csv",
    "Provisioned Apps CSV": "_ProvisionedApps.csv",
    "Default Apps XML": "_DefaultAppAssociations.xml",
    "Default Apps TXT": "_DefaultAppAssociations.txt",
    "Scheduled Tasks CSV": "_ScheduledTasks.csv",
    "Scheduled Tasks TXT": "_ScheduledTasks.txt",
    "Display Audio Camera System CSV": "_Display_Audio_Camera_System.csv",
    "USB TypeC UCSI CSV": "_USB_TypeC_UCSI.csv",
    "Vendor Related Devices CSV": "_Vendor_Related_Devices.csv",
    "EventLog System": "_EventLog_System.evtx",
    "EventLog Application": "_EventLog_Application.evtx",
    "EventLog Kernel PnP Configuration": "_EventLog_KernelPnP_Configuration.evtx",
    "EventLog DriverFrameworks UserMode": "_EventLog_DriverFrameworks_UserMode.evtx",
    "Installed Updates CSV": "_InstalledUpdates.csv",
    "Services CSV": "_Services.csv",
    "Startup Apps CSV": "_StartupApps.csv",
    "Power Plan TXT": "_PowerPlan.txt",
    "IPConfig TXT": "_IPConfig.txt",
    "PnP Interfaces TXT": "_PnpInterfaces.txt",
    "PnP Device Status JSON": "_PnpDeviceStatus.json",
    "PnP Parent Devices CSV": "_PnpParentDevices.csv",
    "Collection Status": "_CollectionStatus.txt",
    "Run Log": "_RunLog.txt",
}


def hide_console_window() -> None:
    """Hide the Windows console when Dowsing is running with its GUI.

    This prevents the legacy black console from sitting behind the Tkinter UI.
    When packaged, using PyInstaller --noconsole is still the cleanest option because
    it prevents the console from being created in the first place.
    """
    if not HIDE_CONSOLE_WHEN_GUI or tk is None or sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


def get_mode_from_args() -> str | None:
    """Read --mode default/debug from command-line arguments."""
    for index, arg in enumerate(sys.argv):
        lower = arg.lower()
        if lower.startswith("--mode="):
            value = lower.split("=", 1)[1]
            if value in {"default", "debug"}:
                return value
        if lower == "--mode" and index + 1 < len(sys.argv):
            value = sys.argv[index + 1].lower()
            if value in {"default", "debug"}:
                return value
    return None


def remember_mode_for_elevation(mode: str) -> None:
    """Ensure the selected mode survives the UAC relaunch."""
    if get_mode_from_args() is None:
        sys.argv.extend(["--mode", mode])


def select_run_mode() -> str | None:
    """Show a small launcher for Default or Debug collection mode.

    Default:
        Collects the structured and summary data currently consumed by Precog.
        It skips redundant raw reports and the slower deep-debug collectors.

    Debug:
        Runs the complete Dowsing collector set.
    """
    if tk is None:
        safe_print("Select Dowsing mode:")
        safe_print("  1. Default - Required Precog data, faster")
        safe_print("  2. Debug   - Full collection, slower")
        try:
            choice = input("Enter 1 or 2: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        return "debug" if choice == "2" else "default" if choice == "1" else None

    selected: dict[str, str | None] = {"mode": None}

    root = tk.Tk()
    root.title("Dowsing")
    root.geometry("520x330")
    root.resizable(False, False)
    root.configure(bg="#f8fafc")

    # Center the window.
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 520) // 2
    y = (root.winfo_screenheight() - 330) // 2
    root.geometry(f"520x330+{x}+{y}")

    def choose(mode: str) -> None:
        selected["mode"] = mode
        root.destroy()

    def cancel() -> None:
        selected["mode"] = None
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", cancel)

    tk.Label(
        root,
        text="Dowsing",
        font=("Segoe UI", 22, "bold"),
        bg="#f8fafc",
        fg="#0f172a",
    ).pack(pady=(24, 4))

    tk.Label(
        root,
        text="Select a collection mode",
        font=("Segoe UI", 11),
        bg="#f8fafc",
        fg="#64748b",
    ).pack(pady=(0, 18))

    default_frame = tk.Frame(root, bg="#ffffff", highlightbackground="#cbd5e1", highlightthickness=1)
    default_frame.pack(fill="x", padx=28, pady=5)

    tk.Button(
        default_frame,
        text="Default",
        command=lambda: choose("default"),
        font=("Segoe UI", 11, "bold"),
        bg="#0f172a",
        fg="#ffffff",
        activebackground="#334155",
        activeforeground="#ffffff",
        relief="flat",
        cursor="hand2",
        width=13,
        pady=9,
    ).pack(side="left", padx=14, pady=14)

    tk.Label(
        default_frame,
        text="Required Precog data\nFaster daily collection",
        justify="left",
        font=("Segoe UI", 10),
        bg="#ffffff",
        fg="#334155",
    ).pack(side="left", padx=(2, 10), pady=12)

    debug_frame = tk.Frame(root, bg="#ffffff", highlightbackground="#cbd5e1", highlightthickness=1)
    debug_frame.pack(fill="x", padx=28, pady=5)

    tk.Button(
        debug_frame,
        text="Debug",
        command=lambda: choose("debug"),
        font=("Segoe UI", 11, "bold"),
        bg="#2563eb",
        fg="#ffffff",
        activebackground="#1d4ed8",
        activeforeground="#ffffff",
        relief="flat",
        cursor="hand2",
        width=13,
        pady=9,
    ).pack(side="left", padx=14, pady=14)

    tk.Label(
        debug_frame,
        text="Complete Dowsing collection\nFor deep investigation",
        justify="left",
        font=("Segoe UI", 10),
        bg="#ffffff",
        fg="#334155",
    ).pack(side="left", padx=(2, 10), pady=12)

    tk.Label(
        root,
        text="Default is recommended for normal Precog use.",
        font=("Segoe UI", 9),
        bg="#f8fafc",
        fg="#64748b",
    ).pack(pady=(13, 0))

    root.mainloop()
    return selected["mode"]


def build_collectors(mode: str) -> List[Tuple[str, Callable[[Path], Tuple[bool, str]]]]:
    """Return the collector set for the selected mode."""

    # Required by the current Precog UI and its structured summaries.
    default_collectors: List[Tuple[str, Callable[[Path], Tuple[bool, str]]]] = [
        ("OS Version", collect_os_version),
        ("Windows Version Reg", collect_windows_version_reg),
        ("DISM Driver Info", collect_dism_driverinfo),
        ("PnP Devices Info", collect_pnp_devices),
        ("PnP Devices CSV", collect_pnp_devices_csv),
        ("PnP Problem Devices", collect_pnp_problem_devices),
        ("PnP Problem Devices CSV", collect_pnp_problem_devices_csv),
        ("Windows Driver CSV", collect_windows_driver_csv),
        ("Catalog Map", collect_catalog_map),
        ("System Summary JSON", collect_system_summary),
        ("Hardware Inventory JSON", collect_hardware_inventory),
        ("PowerCfg Available Sleep States", collect_powercfg_a),
        ("PowerCfg Requests", collect_powercfg_requests),
        ("PowerCfg LastWake", collect_powercfg_lastwake),
        ("PowerCfg Wake Armed", collect_powercfg_wake_armed),
        ("SleepStudy Report", collect_sleepstudy),
        ("Installed Apps", collect_installed_apps),
        ("Default Apps", collect_default_apps),
        ("Scheduled Tasks", collect_scheduled_tasks),
        ("Special Device Groups", collect_special_devices),
        ("Installed Updates", collect_installed_updates),
        ("Services", collect_services),
        ("Startup Apps", collect_startup_apps),
        ("Power Plan", collect_power_plan),
        ("IPConfig", collect_ipconfig),
        ("PnP Interfaces", collect_pnp_interfaces),
    ]

    if mode == "default":
        return default_collectors

    # Full raw reports and longer-running collectors for deep debugging.
    debug_only_collectors: List[Tuple[str, Callable[[Path], Tuple[bool, str]]]] = [
        ("SystemInfo", collect_systeminfo),
        ("BCD Info", collect_bcdinfo),
        ("Driver Query", collect_driver_query),
        ("Driver Query CSV", collect_driver_query_csv),
        ("MSInfo32", collect_msinfo32),
        ("DXDiag", collect_dxdiag),
        ("SetupAPI Device Log", collect_setupapi_dev_log),
        ("Energy Report", collect_energy_report),
        ("Event Logs", collect_event_logs),
    ]

    # Keep the logical order of the original full collection.
    return [
        ("OS Version", collect_os_version),
        ("SystemInfo", collect_systeminfo),
        ("Windows Version Reg", collect_windows_version_reg),
        ("BCD Info", collect_bcdinfo),
        ("DISM Driver Info", collect_dism_driverinfo),
        ("PnP Devices Info", collect_pnp_devices),
        ("PnP Devices CSV", collect_pnp_devices_csv),
        ("PnP Problem Devices", collect_pnp_problem_devices),
        ("PnP Problem Devices CSV", collect_pnp_problem_devices_csv),
        ("Driver Query", collect_driver_query),
        ("Driver Query CSV", collect_driver_query_csv),
        ("Windows Driver CSV", collect_windows_driver_csv),
        ("OEM INF Collection", collect_oem_inf_files),
        ("MSInfo32", collect_msinfo32),
        ("DXDiag", collect_dxdiag),
        ("Catalog Map", collect_catalog_map),
        ("System Summary JSON", collect_system_summary),
        ("Hardware Inventory JSON", collect_hardware_inventory),
        ("SetupAPI Device Log", collect_setupapi_dev_log),
        ("PowerCfg Available Sleep States", collect_powercfg_a),
        ("PowerCfg Requests", collect_powercfg_requests),
        ("PowerCfg LastWake", collect_powercfg_lastwake),
        ("PowerCfg Wake Armed", collect_powercfg_wake_armed),
        ("SleepStudy Report", collect_sleepstudy),
        ("Energy Report", collect_energy_report),
        ("Installed Apps", collect_installed_apps),
        ("Default Apps", collect_default_apps),
        ("Scheduled Tasks", collect_scheduled_tasks),
        ("Special Device Groups", collect_special_devices),
        ("Event Logs", collect_event_logs),
        ("Installed Updates", collect_installed_updates),
        ("Services", collect_services),
        ("Startup Apps", collect_startup_apps),
        ("Power Plan", collect_power_plan),
        ("IPConfig", collect_ipconfig),
        ("PnP Interfaces", collect_pnp_interfaces),
        ("Parent Device Collection", collect_pnp_parent_devices),
        ("PnP Device Status", collect_pnp_device_status),
    ]


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> None:
    script = Path(sys.argv[0]).resolve()
    params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        f'"{script}" {params}',
        None,
        1,
    )
    if rc <= 32:
        raise RuntimeError(f"Failed to elevate process, ShellExecuteW rc={rc}")
    sys.exit(0)


def ensure_admin() -> None:
    if not is_admin():
        safe_print("[INFO] Administrator privilege required. Requesting elevation...")
        relaunch_as_admin()


def run_command(
    cmd: List[str],
    output_path: Path,
    timeout: int = 120,
    shell: bool = False,
    encoding: str = "utf-8",
) -> Tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
            encoding=encoding,
            errors="replace",
            creationflags=SUBPROCESS_CREATIONFLAGS,
        )
        content = result.stdout if result.stdout else result.stderr
        output_path.write_text(content or "", encoding="utf-8", errors="replace")

        if result.returncode != 0:
            return False, f"returncode={result.returncode}"

        if not content.strip():
            return False, "empty output"

        return True, "OK"
    except subprocess.TimeoutExpired:
        output_path.write_text("[TIMEOUT]", encoding="utf-8")
        return False, "timeout"
    except Exception as exc:
        output_path.write_text(f"[EXCEPTION] {exc}", encoding="utf-8")
        return False, str(exc)


def run_powershell(script: str, timeout: int = 180) -> Tuple[bool, str]:
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            creationflags=SUBPROCESS_CREATIONFLAGS,
        )
        content = result.stdout if result.stdout else result.stderr

        if result.returncode != 0:
            return False, content or f"returncode={result.returncode}"

        if not (content or "").strip():
            return False, "empty output"

        return True, content
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as exc:
        return False, str(exc)


def run_external_creates_file(
    cmd: List[str],
    output_path: Path,
    timeout: int = 240,
) -> Tuple[bool, str]:
    """Run a tool that writes directly to output_path, such as msinfo32, dxdiag, powercfg."""
    try:
        subprocess.run(
            cmd,
            timeout=timeout,
            check=True,
            creationflags=SUBPROCESS_CREATIONFLAGS,
        )
        if output_path.exists() and output_path.stat().st_size > 0:
            return True, "OK"
        output_path.write_text("[EMPTY OUTPUT]", encoding="utf-8", errors="replace")
        return False, "empty output"
    except subprocess.TimeoutExpired:
        output_path.write_text("[TIMEOUT]", encoding="utf-8")
        return False, "timeout"
    except Exception as exc:
        output_path.write_text(f"[EXCEPTION] {exc}", encoding="utf-8", errors="replace")
        return False, str(exc)


def collect_os_version(out_dir: Path) -> Tuple[bool, str]:
    return run_command(["cmd", "/c", "ver"], out_dir / OUTPUT_FILES["OS Version"])


def collect_systeminfo(out_dir: Path) -> Tuple[bool, str]:
    return run_command(["systeminfo"], out_dir / OUTPUT_FILES["SystemInfo"], timeout=180)


def collect_windows_version_reg(out_dir: Path) -> Tuple[bool, str]:
    return run_command(
        ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion"],
        out_dir / OUTPUT_FILES["Windows Version Reg"],
    )


def collect_bcdinfo(out_dir: Path) -> Tuple[bool, str]:
    return run_command(["bcdedit", "/enum", "all"], out_dir / OUTPUT_FILES["BCD Info"])


def collect_dism_driverinfo(out_dir: Path) -> Tuple[bool, str]:
    return run_command(
        ["dism", "/online", "/get-drivers", "/format:table"],
        out_dir / OUTPUT_FILES["DISM Driver Info"],
        timeout=180,
    )


def collect_pnp_devices(out_dir: Path) -> Tuple[bool, str]:
    return run_command(
        ["pnputil", "/enum-devices", "/drivers", "/ids"],
        out_dir / OUTPUT_FILES["PnP Devices Info"],
        timeout=180,
    )


def collect_pnp_devices_csv(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["PnP Devices CSV"]
    ps_script = r"""
Get-PnpDevice |
    Sort-Object Class,FriendlyName |
    Select-Object Class,FriendlyName,InstanceId,Status,Problem,ConfigManagerErrorCode |
    ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(ps_script, timeout=180)
    path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    return (ok and path.stat().st_size > 0), ("OK" if ok else content)


def collect_pnp_problem_devices(out_dir: Path) -> Tuple[bool, str]:
    return run_command(
        ["pnputil", "/enum-devices", "/problem"],
        out_dir / OUTPUT_FILES["PnP Problem Devices"],
        timeout=120,
    )


def collect_pnp_problem_devices_csv(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["PnP Problem Devices CSV"]
    ps_script = r"""
Get-PnpDevice |
    Where-Object { $_.Status -ne 'OK' } |
    Sort-Object Class,FriendlyName |
    Select-Object Class,FriendlyName,InstanceId,Status,Problem,ConfigManagerErrorCode |
    ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(ps_script, timeout=180)
    # Empty output is acceptable when there are no problem devices, so write a header instead.
    if ok and not content.strip():
        content = '"Class","FriendlyName","InstanceId","Status","Problem","ConfigManagerErrorCode"\n'
    path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    return True if path.exists() and path.stat().st_size > 0 else False, "OK"


def collect_driver_query(out_dir: Path) -> Tuple[bool, str]:
    return run_command(["driverquery", "/v"], out_dir / OUTPUT_FILES["Driver Query"], timeout=180)


def collect_driver_query_csv(out_dir: Path) -> Tuple[bool, str]:
    return run_command(
        ["driverquery", "/v", "/fo", "csv"],
        out_dir / OUTPUT_FILES["Driver Query CSV"],
        timeout=180,
    )


def collect_windows_driver_csv(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["Windows Driver CSV"]
    ps_script = r"""
Get-WindowsDriver -Online -All |
    Sort-Object ProviderName,ClassName,Driver |
    Select-Object Driver,OriginalFileName,Inbox,ClassName,ProviderName,Date,Version,BootCritical |
    ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(ps_script, timeout=240)
    path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    return (ok and path.stat().st_size > 0), ("OK" if ok else content)


def collect_oem_inf_files(out_dir: Path) -> Tuple[bool, str]:
    """Collect published OEM INF files for Precog Driver Status deep inspection.

    Debug mode only. Files are copied from %WINDIR%\\INF\\oem*.inf into:
        OEM_INF\\oem0.inf
        OEM_INF\\oem1.inf
        ...

    Only the published INF text files are collected; PNF files and other
    DriverStore payloads are intentionally excluded.
    """
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    source_dir = windows_dir / "INF"
    target_dir = out_dir / "OEM_INF"

    try:
        if not source_dir.exists():
            return False, f"source not found: {source_dir}"

        inf_files = sorted(
            source_dir.glob("oem*.inf"),
            key=lambda p: (
                int(p.stem[3:]) if p.stem[3:].isdigit() else 10**9,
                p.name.lower(),
            ),
        )

        if not inf_files:
            return False, "no OEM INF files found"

        target_dir.mkdir(parents=True, exist_ok=True)

        copied = 0
        failed = []

        for source in inf_files:
            try:
                shutil.copy2(source, target_dir / source.name)
                copied += 1
            except Exception as exc:
                failed.append(f"{source.name}: {exc}")

        if copied == 0:
            return False, "failed to copy OEM INF files"

        if failed:
            return True, f"Copied {copied}/{len(inf_files)} OEM INF files; {len(failed)} failed"

        return True, f"Copied {copied} OEM INF files"

    except Exception as exc:
        return False, str(exc)


def collect_msinfo32(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["MSInfo32 Report"]
    return run_external_creates_file(["msinfo32.exe", "/report", str(path)], path, timeout=240)


def collect_dxdiag(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["DXDiag Report"]
    return run_external_creates_file(["dxdiag.exe", "/t", str(path)], path, timeout=240)


def collect_catalog_map(out_dir: Path) -> Tuple[bool, str]:
    """
    Align with old PS1:
    Get-WindowsDriver -Online |
    Select Driver, OriginalFileName, CatalogFile, ClassName, ProviderName, Date, Version |
    Export-Csv
    """
    path = out_dir / OUTPUT_FILES["Catalog Map"]

    ps_script = r"""
$drivers = Get-WindowsDriver -Online |
    Select-Object Driver, OriginalFileName, CatalogFile, ClassName, ProviderName, Date, Version

if (-not $drivers) {
    throw 'Get-WindowsDriver returned no data.'
}

$drivers | ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(ps_script, timeout=240)
    path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    return (ok and path.stat().st_size > 0), ("OK" if ok else content)


def collect_system_summary(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["System Summary JSON"]

    ps_script = r"""
$computer = Get-CimInstance -ClassName Win32_ComputerSystem
$bios = Get-CimInstance -ClassName Win32_BIOS
$os = Get-CimInstance -ClassName Win32_OperatingSystem
$baseboard = Get-CimInstance -ClassName Win32_BaseBoard

$secureBoot = 'Unknown'
try {
    $sb = Confirm-SecureBootUEFI
    $secureBoot = if ($sb) { 'On' } else { 'Off' }
}
catch {
    $secureBoot = 'Unsupported/Unknown'
}

$obj = [ordered]@{
    ComputerName = $env:COMPUTERNAME
    Manufacturer = $computer.Manufacturer
    Model = $computer.Model
    SystemSKU = $computer.SystemSKUNumber
    BaseBoardProduct = $baseboard.Product
    BaseBoardVersion = $baseboard.Version
    BIOSVersion = (($bios.SMBIOSBIOSVersion, $bios.Version -ne $null) | ForEach-Object { $_ }) -join ' | '
    BIOSReleaseDate = $bios.ReleaseDate
    OSName = $os.Caption
    OSVersion = $os.Version
    OSBuild = $os.BuildNumber
    TotalPhysicalMemoryGB = [math]::Round(($computer.TotalPhysicalMemory / 1GB), 2)
    SecureBoot = $secureBoot
    Timestamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
}

$obj | ConvertTo-Json -Depth 4
"""
    ok, content = run_powershell(ps_script, timeout=180)

    try:
        if ok:
            json.loads(content)
            path.write_text(content, encoding="utf-8", errors="replace")
            return True, "OK"
        path.write_text(content or "", encoding="utf-8", errors="replace")
        return False, content
    except Exception as exc:
        path.write_text(f"[EXCEPTION] {exc}\n{content}", encoding="utf-8", errors="replace")
        return False, str(exc)


def collect_hardware_inventory(out_dir: Path) -> Tuple[bool, str]:
    """Create _HardwareInventory.json for Precog.

    T06 policy:
    - Display / Panel: use WmiMonitorID and render as vendor + panel model.
      If WmiMonitorID has no UserFriendlyName, fall back to EDID/PnP ID-like code
      such as SHP1589, AUOBB9D, BOE0A3C.
    - Network: use Get-NetAdapter, prefer InterfaceDescription as DisplayName,
      and filter Bluetooth PAN / Virtual / VPN / Wi-Fi Direct / WAN Miniport noise.
    """
    path = out_dir / OUTPUT_FILES["Hardware Inventory JSON"]

    ps_script = r"""
function ConvertTo-SafeArray($value) {
    if ($null -eq $value) { return @() }
    return @($value)
}

function Decode-UInt16Ascii($arr) {
    if ($null -eq $arr) { return '' }
    $chars = @($arr) | Where-Object { $_ -ne 0 } | ForEach-Object { [char][int]$_ }
    return (($chars -join '')).Trim()
}

function Normalize-PanelVendor($vendor) {
    if ([string]::IsNullOrWhiteSpace($vendor)) { return 'Unknown' }

    $v = $vendor.Trim().ToUpperInvariant()

    $map = @{
        'AUO' = 'AUO'
        'BOE' = 'BOE'
        'LGD' = 'LG'
        'LPL' = 'LG'
        'CMN' = 'CMN'
        'CSO' = 'CSO'
        'SDC' = 'SDC'
        'SEC' = 'SEC'
        'SHP' = 'Sharp'
        'IVO' = 'IVO'
        'INX' = 'INX'
        'HKC' = 'HKC'
        'MS_' = 'Microsoft'
    }

    if ($map.ContainsKey($v)) { return $map[$v] }
    return $v
}

function Get-PanelCodeFromInstanceName($instanceName) {
    if ([string]::IsNullOrWhiteSpace($instanceName)) { return '' }

    # Example:
    # DISPLAY\SHP1589\5&...
    # DISPLAY\AUOBB9D\...
    if ($instanceName -match 'DISPLAY\\([^\\]+)\\') {
        return $matches[1]
    }

    return ''
}

function Select-PnpDeviceFields($devices) {
    ConvertTo-SafeArray $devices |
        Where-Object { $_ -ne $null } |
        Sort-Object Class,FriendlyName,InstanceId |
        Select-Object Class,FriendlyName,InstanceId,Status,Problem,ConfigManagerErrorCode
}

function Get-PnpGroup($namePattern, $classPattern, $idPattern, [switch]$OnlyPresent) {
    $all = Get-PnpDevice -ErrorAction SilentlyContinue

    $devices = $all | Where-Object {
        (($namePattern -and $_.FriendlyName -and $_.FriendlyName -match $namePattern) -or
         ($classPattern -and $_.Class -and $_.Class -match $classPattern) -or
         ($idPattern -and $_.InstanceId -and $_.InstanceId -match $idPattern))
    }

    if ($OnlyPresent) {
        $devices = $devices | Where-Object { $_.Status -eq 'OK' }
    }

    Select-PnpDeviceFields $devices
}

function Get-PanelInventory {
    $monitors = @()

    try {
        $wmiMonitors = Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID -ErrorAction Stop |
            Where-Object { $_.Active -eq $true -or $null -eq $_.Active }

        foreach ($m in $wmiMonitors) {
            $rawVendor = Decode-UInt16Ascii $m.ManufacturerName
            $vendor = Normalize-PanelVendor $rawVendor
            $model = Decode-UInt16Ascii $m.UserFriendlyName
            $serial = Decode-UInt16Ascii $m.SerialNumberID
            $productCode = Decode-UInt16Ascii $m.ProductCodeID
            $panelCode = Get-PanelCodeFromInstanceName $m.InstanceName

            $displayName = ''
            if (-not [string]::IsNullOrWhiteSpace($model)) {
                if ($model -match "^\Q$vendor\E\s+") {
                    $displayName = $model
                }
                else {
                    $displayName = (($vendor, $model) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ' '
                }
            }
            elseif (-not [string]::IsNullOrWhiteSpace($panelCode)) {
                # This gives useful output like Sharp SHP1589 / AUO AUOBB9D instead of "Monitor".
                $displayName = (($vendor, $panelCode) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and $_ -ne 'Unknown' }) -join ' '
                if ([string]::IsNullOrWhiteSpace($displayName)) { $displayName = $panelCode }
            }
            elseif (-not [string]::IsNullOrWhiteSpace($productCode)) {
                $displayName = (($vendor, $productCode) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and $_ -ne 'Unknown' }) -join ' '
                if ([string]::IsNullOrWhiteSpace($displayName)) { $displayName = $productCode }
            }
            else {
                $displayName = $vendor
            }

            $monitors += [PSCustomObject]@{
                DisplayName = $displayName
                Manufacturer = $vendor
                RawManufacturer = $rawVendor
                Model = $model
                ProductCode = $productCode
                PanelCode = $panelCode
                SerialNumber = $serial
                InstanceName = $m.InstanceName
                Active = $m.Active
                Source = 'WmiMonitorID'
            }
        }
    }
    catch {
        # WmiMonitorID may fail on some environments. Fall back to present DISPLAY PnP entries only.
        $pnpMonitors = Get-PnpDevice -ErrorAction SilentlyContinue |
            Where-Object { $_.Class -eq 'Monitor' -and $_.Status -eq 'OK' -and $_.InstanceId -like 'DISPLAY*' }

        foreach ($p in $pnpMonitors) {
            $panelCode = Get-PanelCodeFromInstanceName $p.InstanceId
            $vendor3 = if ($panelCode.Length -ge 3) { $panelCode.Substring(0,3) } else { '' }
            $vendor = Normalize-PanelVendor $vendor3
            $displayName = (($vendor, $panelCode) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and $_ -ne 'Unknown' }) -join ' '
            if ([string]::IsNullOrWhiteSpace($displayName)) { $displayName = if ($p.FriendlyName) { $p.FriendlyName } else { $p.InstanceId } }

            $monitors += [PSCustomObject]@{
                DisplayName = $displayName
                Manufacturer = $vendor
                RawManufacturer = $vendor3
                Model = ''
                ProductCode = ''
                PanelCode = $panelCode
                SerialNumber = ''
                InstanceName = $p.InstanceId
                Active = $true
                Source = 'PnPDeviceFallback'
            }
        }
    }

    return ConvertTo-SafeArray $monitors
}

function Get-NetworkInventory {
    $adapters = @()

    try {
        $netAdapters = Get-NetAdapter -ErrorAction Stop |
            Where-Object {
                $_.InterfaceDescription -and
                $_.InterfaceDescription -notmatch 'WAN Miniport|Bluetooth|Personal Area Network|Wi-Fi Direct|Hyper-V|Virtual|VPN|TAP|TUN|Loopback|Microsoft Kernel Debug|QoS Packet Scheduler|Npcap|Packet Capture'
            }

        foreach ($a in $netAdapters) {
            $desc = [string]$a.InterfaceDescription
            $name = [string]$a.Name
            $type = 'Other'

            if ($desc -match 'Wireless|Wi-Fi|WLAN|802\.11|BE200|AX2|Realtek.*Wireless|MediaTek.*Wi|Qualcomm.*Wireless|RZ[0-9]|Killer.*Wi') {
                $type = 'WLAN'
            }
            elseif ($desc -match 'Ethernet|GbE|2\.5G|5G|10G|I219|I225|I226|Realtek PCIe|Intel.*Ethernet|LAN|Gaming.*Controller') {
                $type = 'LAN'
            }
            elseif ($desc -match 'Hyper-V|Virtual|VPN|TAP|TUN|Loopback|Wi-Fi Direct|Bluetooth') {
                $type = 'Virtual'
            }

            if ($type -ne 'Virtual' -and $type -ne 'Other') {
                $adapters += [PSCustomObject]@{
                    DisplayName = $desc
                    Name = $name
                    InterfaceDescription = $desc
                    Type = $type
                    Status = [string]$a.Status
                    MacAddress = $a.MacAddress
                    LinkSpeed = $a.LinkSpeed
                    InterfaceGuid = $a.InterfaceGuid
                    ifIndex = $a.ifIndex
                    Source = 'Get-NetAdapter'
                }
            }
        }
    }
    catch {
        $fallback = Get-PnpGroup 'Ethernet|LAN|GbE|I219|I225|I226|Realtek PCIe|Intel.*Ethernet|Wi-Fi|Wireless|WLAN|802\.11|Intel.*Wireless|Realtek.*Wireless|MediaTek.*Wi' 'Net' 'PCI\\VEN|USB' -OnlyPresent
        foreach ($f in $fallback) {
            $type = 'Other'
            $name = if ($f.FriendlyName) { $f.FriendlyName } else { $f.InstanceId }

            if ($name -match 'Wi-Fi|Wireless|WLAN|802\.11') { $type = 'WLAN' }
            elseif ($name -match 'Ethernet|LAN|GbE|I219|I225|I226') { $type = 'LAN' }

            if ($type -ne 'Other' -and $name -notmatch 'Bluetooth|Virtual|Wi-Fi Direct|WAN Miniport') {
                $adapters += [PSCustomObject]@{
                    DisplayName = $name
                    Name = $name
                    InterfaceDescription = $name
                    Type = $type
                    Status = $f.Status
                    MacAddress = ''
                    LinkSpeed = ''
                    InterfaceGuid = ''
                    ifIndex = ''
                    Source = 'PnPDeviceFallback'
                }
            }
        }
    }

    return ConvertTo-SafeArray $adapters
}

function Get-AudioInventory {
    # Focus on real audio controller/function devices. Avoid AudioEndpoint Speaker/Microphone noise.
    $devices = Get-PnpDevice -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Status -eq 'OK' -and
            (
                ($_.Class -match 'MEDIA|Sound') -or
                ($_.InstanceId -match 'HDAUDIO|INTELAUDIO|ACP|VEN_10EC|VEN_1002|VEN_10DE') -or
                ($_.FriendlyName -match 'Realtek.*Audio|Intel.*Smart Sound|AMD.*Audio|NVIDIA.*Audio|High Definition Audio')
            ) -and
            ($_.Class -notmatch 'AudioEndpoint') -and
            ($_.FriendlyName -notmatch 'Speakers|Speaker|Microphone|Headphones|Headset|Line In|HDMI Output')
        }

    return Select-PnpDeviceFields $devices
}

function Get-BluetoothInventory {
    $devices = Get-PnpDevice -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Status -eq 'OK' -and
            (
                ($_.Class -eq 'Bluetooth') -or
                ($_.FriendlyName -match 'Intel.*Bluetooth|Realtek.*Bluetooth|MediaTek.*Bluetooth|Qualcomm.*Bluetooth|Bluetooth Adapter')
            ) -and
            ($_.FriendlyName -notmatch 'Enumerator|Protocol|Service|RFCOMM|LE Generic Attribute|Personal Area Network')
        }

    return Select-PnpDeviceFields $devices
}

function Get-UsbInventory {
    # Keep USB controller / Type-C / UCSI relevant devices, not every USB child device.
    $devices = Get-PnpDevice -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Status -eq 'OK' -and
            (
                ($_.FriendlyName -match 'USB.*Host Controller|USB.*Root Hub|xHCI|UCSI|UCM|Type-C|Billboard') -or
                ($_.InstanceId -match 'USBC000|UCM|USB\\ROOT|USB\\VID_.*&PID_.*BILLBOARD')
            )
        }

    return Select-PnpDeviceFields $devices
}

$computer = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction SilentlyContinue
$bios = Get-CimInstance -ClassName Win32_BIOS -ErrorAction SilentlyContinue
$baseboard = Get-CimInstance -ClassName Win32_BaseBoard -ErrorAction SilentlyContinue
$os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction SilentlyContinue

$cpu = Get-CimInstance -ClassName Win32_Processor -ErrorAction SilentlyContinue |
    Select-Object Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,SocketDesignation,ProcessorId

$memoryModules = Get-CimInstance -ClassName Win32_PhysicalMemory -ErrorAction SilentlyContinue |
    Select-Object BankLabel,DeviceLocator,Manufacturer,PartNumber,SerialNumber,Capacity,Speed,ConfiguredClockSpeed,MemoryType,SMBIOSMemoryType

$physicalDisks = Get-CimInstance -ClassName Win32_DiskDrive -ErrorAction SilentlyContinue |
    Select-Object Model,Manufacturer,SerialNumber,InterfaceType,MediaType,Size,FirmwareRevision,PNPDeviceID

$logicalDisks = Get-CimInstance -ClassName Win32_LogicalDisk -ErrorAction SilentlyContinue |
    Select-Object DeviceID,VolumeName,FileSystem,Size,FreeSpace,DriveType

$graphics = Get-CimInstance -ClassName Win32_VideoController -ErrorAction SilentlyContinue |
    Select-Object Name,AdapterCompatibility,PNPDeviceID,DriverVersion,VideoProcessor,AdapterRAM,CurrentHorizontalResolution,CurrentVerticalResolution

$batteryCim = Get-CimInstance -ClassName Win32_Battery -ErrorAction SilentlyContinue |
    Select-Object Name,DeviceID,Status,BatteryStatus,EstimatedChargeRemaining,DesignVoltage

$tpmCim = Get-CimInstance -Namespace root\CIMV2\Security\MicrosoftTpm -ClassName Win32_Tpm -ErrorAction SilentlyContinue |
    Select-Object SpecVersion,ManufacturerId,ManufacturerIdTxt,ManufacturerVersion,IsEnabled_InitialValue,IsActivated_InitialValue,IsOwned_InitialValue

$secureBoot = 'Unknown'
try {
    $sb = Confirm-SecureBootUEFI
    $secureBoot = if ($sb) { 'On' } else { 'Off' }
} catch {
    $secureBoot = 'Unsupported/Unknown'
}

$displayPanels = Get-PanelInventory
$networkAdapters = Get-NetworkInventory

$obj = [ordered]@{
    SchemaVersion = 'Precog.HardwareInventory.T06'
    Timestamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    System = [ordered]@{
        ComputerName = $env:COMPUTERNAME
        Manufacturer = $computer.Manufacturer
        Model = $computer.Model
        SystemSKU = $computer.SystemSKUNumber
        SystemFamily = $computer.SystemFamily
        BaseBoardProduct = $baseboard.Product
        BaseBoardVersion = $baseboard.Version
        BIOSVersion = (($bios.SMBIOSBIOSVersion, $bios.Version -ne $null) | ForEach-Object { $_ }) -join ' | '
        BIOSReleaseDate = $bios.ReleaseDate
        OSName = $os.Caption
        OSVersion = $os.Version
        OSBuild = $os.BuildNumber
        SecureBoot = $secureBoot
    }
    CPU = ConvertTo-SafeArray $cpu
    Memory = [ordered]@{
        TotalPhysicalMemoryBytes = $computer.TotalPhysicalMemory
        Modules = ConvertTo-SafeArray $memoryModules
    }
    Storage = [ordered]@{
        PhysicalDisks = ConvertTo-SafeArray $physicalDisks
        LogicalDisks = ConvertTo-SafeArray $logicalDisks
    }
    Graphics = ConvertTo-SafeArray $graphics
    Display = [ordered]@{
        Monitors = ConvertTo-SafeArray $displayPanels
        Panel = ConvertTo-SafeArray $displayPanels
    }
    Network = [ordered]@{
        Adapters = ConvertTo-SafeArray $networkAdapters
        WLAN = ConvertTo-SafeArray ($networkAdapters | Where-Object { $_.Type -eq 'WLAN' })
        LAN = ConvertTo-SafeArray ($networkAdapters | Where-Object { $_.Type -eq 'LAN' })
        Bluetooth = ConvertTo-SafeArray (Get-BluetoothInventory)
    }
    Audio = ConvertTo-SafeArray (Get-AudioInventory)
    Camera = ConvertTo-SafeArray (Get-PnpGroup 'Camera|Webcam|IR Camera|RGB Camera' 'Camera|Image' 'USB|ACPI' -OnlyPresent)
    Battery = ConvertTo-SafeArray $batteryCim
    TPM = ConvertTo-SafeArray $tpmCim
    USB = ConvertTo-SafeArray (Get-UsbInventory)
    Security = [ordered]@{
        SecureBoot = $secureBoot
        TPM = ConvertTo-SafeArray $tpmCim
    }
}

$obj | ConvertTo-Json -Depth 10
"""
    ok, content = run_powershell(ps_script, timeout=240)

    try:
        if ok:
            json.loads(content)
            path.write_text(content, encoding="utf-8", errors="replace")
            return True, "OK"
        path.write_text(content or "", encoding="utf-8", errors="replace")
        return False, content
    except Exception as exc:
        path.write_text(f"[EXCEPTION] {exc}\n{content}", encoding="utf-8", errors="replace")
        return False, str(exc)

def collect_setupapi_dev_log(out_dir: Path) -> Tuple[bool, str]:
    return copy_file(Path(r"C:\Windows\INF\setupapi.dev.log"), out_dir / OUTPUT_FILES["SetupAPI Device Log"])


def copy_file(src: Path, dst: Path) -> Tuple[bool, str]:
    try:
        if not src.exists():
            dst.write_text("[NOT FOUND]", encoding="utf-8")
            return False, "source not found"
        shutil.copy2(src, dst)
        if not dst.exists() or dst.stat().st_size == 0:
            return False, "empty output"
        return True, "OK"
    except Exception as exc:
        dst.write_text(f"[EXCEPTION] {exc}", encoding="utf-8")
        return False, str(exc)


def collect_powercfg_a(out_dir: Path) -> Tuple[bool, str]:
    return run_command(["powercfg", "/a"], out_dir / OUTPUT_FILES["PowerCfg Available Sleep States"], timeout=120)


def collect_powercfg_requests(out_dir: Path) -> Tuple[bool, str]:
    return run_command(["powercfg", "/requests"], out_dir / OUTPUT_FILES["PowerCfg Requests"], timeout=120)


def collect_powercfg_lastwake(out_dir: Path) -> Tuple[bool, str]:
    return run_command(["powercfg", "/lastwake"], out_dir / OUTPUT_FILES["PowerCfg LastWake"], timeout=120)


def collect_powercfg_wake_armed(out_dir: Path) -> Tuple[bool, str]:
    return run_command(["powercfg", "/devicequery", "wake_armed"], out_dir / OUTPUT_FILES["PowerCfg Wake Armed"], timeout=120)


def collect_sleepstudy(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["SleepStudy Report"]
    return run_external_creates_file(
        ["powercfg", "/sleepstudy", "/output", str(path), "/duration", "3"],
        path,
        timeout=240,
    )


def collect_energy_report(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["Energy Report"]
    return run_external_creates_file(
        ["powercfg", "/energy", "/output", str(path), "/duration", "60"],
        path,
        timeout=120,
    )


def collect_installed_apps(out_dir: Path) -> Tuple[bool, str]:
    """Collect both classic Win32 uninstall entries and Appx packages."""
    errors: List[str] = []

    win32_path = out_dir / OUTPUT_FILES["Installed Apps Win32 CSV"]
    win32_script = r"""
$paths = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
)

$apps = foreach ($path in $paths) {
    Get-ItemProperty $path -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName } |
        Select-Object @{Name='Source';Expression={$path}},DisplayName,DisplayVersion,Publisher,InstallDate,InstallLocation,UninstallString,QuietUninstallString,SystemComponent,ReleaseType,WindowsInstaller,PSChildName
}

if (-not $apps) {
    '"Source","DisplayName","DisplayVersion","Publisher","InstallDate","InstallLocation","UninstallString","QuietUninstallString","SystemComponent","ReleaseType","WindowsInstaller","PSChildName"'
}
else {
    $apps | Sort-Object DisplayName,DisplayVersion,Publisher | ConvertTo-Csv -NoTypeInformation
}
"""
    ok, content = run_powershell(win32_script, timeout=180)
    win32_path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    if not ok:
        errors.append(f"Win32 apps: {content}")

    appx_path = out_dir / OUTPUT_FILES["Installed Apps Appx CSV"]
    appx_script = r"""
Get-AppxPackage -AllUsers |
    Sort-Object Name,PackageFullName |
    Select-Object Name,PackageFullName,PackageFamilyName,Publisher,Version,Architecture,ResourceId,InstallLocation,SignatureKind,Status,IsFramework,NonRemovable |
    ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(appx_script, timeout=240)
    appx_path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    if not ok:
        errors.append(f"Appx apps: {content}")

    provisioned_path = out_dir / OUTPUT_FILES["Provisioned Apps CSV"]
    provisioned_script = r"""
Get-AppxProvisionedPackage -Online |
    Sort-Object DisplayName,PackageName |
    Select-Object DisplayName,PackageName,Version,Architecture,ResourceId,InstallLocation,Regions |
    ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(provisioned_script, timeout=240)
    provisioned_path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    if not ok:
        errors.append(f"Provisioned apps: {content}")

    return (len(errors) == 0), "OK" if not errors else " | ".join(errors)


def collect_default_apps(out_dir: Path) -> Tuple[bool, str]:
    """Export default app associations. DISM writes XML directly; TXT is a readable fallback."""
    xml_path = out_dir / OUTPUT_FILES["Default Apps XML"]
    txt_path = out_dir / OUTPUT_FILES["Default Apps TXT"]

    ok, detail = run_external_creates_file(
        ["dism", "/online", f"/Export-DefaultAppAssociations:{xml_path}"],
        xml_path,
        timeout=180,
    )

    if xml_path.exists() and xml_path.stat().st_size > 0:
        try:
            txt_path.write_text(xml_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8", errors="replace")
        except Exception as exc:
            txt_path.write_text(f"[EXCEPTION] {exc}", encoding="utf-8", errors="replace")
        return True, "OK"

    txt_path.write_text(detail or "[NO DEFAULT APP ASSOCIATIONS EXPORTED]", encoding="utf-8", errors="replace")
    return ok, detail


def collect_scheduled_tasks(out_dir: Path) -> Tuple[bool, str]:
    errors: List[str] = []

    csv_path = out_dir / OUTPUT_FILES["Scheduled Tasks CSV"]
    ps_script = r"""
Get-ScheduledTask |
    ForEach-Object {
        $task = $_
        $info = $null
        try { $info = $task | Get-ScheduledTaskInfo -ErrorAction Stop } catch {}

        $actionsText = ''
        try {
            $actionsText = @($task.Actions) |
                Where-Object { $_ -ne $null } |
                ForEach-Object {
                    $execute = if ($_.PSObject.Properties.Name -contains 'Execute') { $_.Execute } else { '' }
                    $arguments = if ($_.PSObject.Properties.Name -contains 'Arguments') { $_.Arguments } else { '' }
                    (($execute, $arguments) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }) -join ' '
                } |
                Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }
            $actionsText = @($actionsText) -join ' | '
        } catch { $actionsText = '' }

        $triggersText = ''
        try {
            $triggersText = @($task.Triggers) |
                Where-Object { $_ -ne $null } |
                ForEach-Object { $_.ToString() }
            $triggersText = @($triggersText) -join ' | '
        } catch { $triggersText = '' }

        [PSCustomObject]@{
            TaskPath = $task.TaskPath
            TaskName = $task.TaskName
            State = $task.State
            Author = $task.Author
            Description = $task.Description
            LastRunTime = if ($info) { $info.LastRunTime } else { $null }
            LastTaskResult = if ($info) { $info.LastTaskResult } else { $null }
            NextRunTime = if ($info) { $info.NextRunTime } else { $null }
            NumberOfMissedRuns = if ($info) { $info.NumberOfMissedRuns } else { $null }
            Actions = $actionsText
            Triggers = $triggersText
        }
    } |
    Sort-Object TaskPath,TaskName |
    ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(ps_script, timeout=240)
    csv_path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    if not ok:
        errors.append(f"ScheduledTasks CSV: {content}")

    txt_path = out_dir / OUTPUT_FILES["Scheduled Tasks TXT"]
    ok, detail = run_command(["schtasks", "/query", "/fo", "LIST", "/v"], txt_path, timeout=240)
    if not ok:
        errors.append(f"schtasks: {detail}")

    return (len(errors) == 0), "OK" if not errors else " | ".join(errors)


def collect_special_devices(out_dir: Path) -> Tuple[bool, str]:
    scripts = {
        "Display Audio Camera System CSV": r"""
Get-PnpDevice |
    Where-Object { $_.Class -match 'Display|Monitor|Media|Audio|Camera|Image|System' } |
    Sort-Object Class,FriendlyName |
    Select-Object Class,FriendlyName,InstanceId,Status,Problem,ConfigManagerErrorCode |
    ConvertTo-Csv -NoTypeInformation
""",
        "USB TypeC UCSI CSV": r"""
Get-PnpDevice |
    Where-Object { $_.FriendlyName -match 'UCSI|UCM|USB|Type-C|Billboard' -or $_.InstanceId -match 'USBC000|USB|UCM' } |
    Sort-Object Class,FriendlyName |
    Select-Object Class,FriendlyName,InstanceId,Status,Problem,ConfigManagerErrorCode |
    ConvertTo-Csv -NoTypeInformation
""",
        "Vendor Related Devices CSV": r"""
Get-PnpDevice |
    Where-Object { $_.FriendlyName -match 'AMD|NVIDIA|Realtek|MediaTek|Intel|Dolby|Camera|Microphone|Audio|ACP|PSP|SMBus|UCSI|UCM' -or $_.InstanceId -match 'AMDI|NVDA|VEN_1022|VEN_10DE|VEN_10EC|USBC000' } |
    Sort-Object Class,FriendlyName |
    Select-Object Class,FriendlyName,InstanceId,Status,Problem,ConfigManagerErrorCode |
    ConvertTo-Csv -NoTypeInformation
""",
    }

    errors: List[str] = []
    for key, script in scripts.items():
        path = out_dir / OUTPUT_FILES[key]
        ok, content = run_powershell(script, timeout=180)
        path.write_text(content or "", encoding="utf-8-sig", errors="replace")
        if not ok:
            errors.append(f"{key}: {content}")
    return (len(errors) == 0), "OK" if not errors else " | ".join(errors)


def export_event_log(log_name: str, output_path: Path) -> Tuple[bool, str]:
    try:
        result = subprocess.run(
            ["wevtutil", "epl", log_name, str(output_path)],
            capture_output=True,
            text=True,
            timeout=180,
            encoding="utf-8",
            errors="replace",
            creationflags=SUBPROCESS_CREATIONFLAGS,
        )
        if result.returncode != 0:
            output_path.with_suffix(output_path.suffix + ".txt").write_text(
                result.stderr or result.stdout or f"returncode={result.returncode}",
                encoding="utf-8",
                errors="replace",
            )
            return False, f"returncode={result.returncode}"
        if output_path.exists() and output_path.stat().st_size > 0:
            return True, "OK"
        return False, "empty output"
    except subprocess.TimeoutExpired:
        output_path.with_suffix(output_path.suffix + ".txt").write_text("[TIMEOUT]", encoding="utf-8")
        return False, "timeout"
    except Exception as exc:
        output_path.with_suffix(output_path.suffix + ".txt").write_text(f"[EXCEPTION] {exc}", encoding="utf-8")
        return False, str(exc)


def collect_event_logs(out_dir: Path) -> Tuple[bool, str]:
    logs = [
        ("System", "EventLog System"),
        ("Application", "EventLog Application"),
        ("Microsoft-Windows-Kernel-PnP/Configuration", "EventLog Kernel PnP Configuration"),
        ("Microsoft-Windows-DriverFrameworks-UserMode/Operational", "EventLog DriverFrameworks UserMode"),
    ]

    errors: List[str] = []
    for log_name, file_key in logs:
        ok, detail = export_event_log(log_name, out_dir / OUTPUT_FILES[file_key])
        if not ok:
            errors.append(f"{log_name}: {detail}")
    return (len(errors) == 0), "OK" if not errors else " | ".join(errors)



def collect_installed_updates(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["Installed Updates CSV"]
    ps = r"""
Get-HotFix |
    Sort-Object InstalledOn |
    Select HotFixID,Description,InstalledBy,InstalledOn |
    ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(ps, timeout=120)
    path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    return (ok and path.stat().st_size > 0), ("OK" if ok else content)


def collect_services(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["Services CSV"]
    ps = r"""
Get-Service |
    Sort-Object DisplayName |
    Select Name,DisplayName,Status,StartType |
    ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(ps, timeout=120)
    path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    return (ok and path.stat().st_size > 0), ("OK" if ok else content)


def collect_startup_apps(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["Startup Apps CSV"]
    ps = r"""
Get-CimInstance Win32_StartupCommand |
    Select Name,Command,Location,User |
    ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(ps, timeout=120)
    path.write_text(content or "", encoding="utf-8-sig", errors="replace")
    return (ok and path.stat().st_size > 0), ("OK" if ok else content)


def collect_power_plan(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["Power Plan TXT"]
    ok1, d1 = run_command(["powercfg", "/list"], path)
    try:
        existing = path.read_text(encoding="utf-8", errors="replace")
    except:
        existing = ""
    ok2, d2 = run_powershell("powercfg /query")
    path.write_text(existing + "\n\n===== powercfg /query =====\n" + (d2 or ""), encoding="utf-8", errors="replace")
    return (ok1 or ok2), "OK"


def collect_ipconfig(out_dir: Path) -> Tuple[bool, str]:
    return run_command(["ipconfig", "/all"], out_dir / OUTPUT_FILES["IPConfig TXT"], timeout=120)


def collect_pnp_interfaces(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["PnP Interfaces TXT"]
    return run_command(["pnputil", "/enum-interfaces"], path, timeout=180)


def collect_pnp_parent_devices(out_dir: Path) -> Tuple[bool, str]:
    """Collect the parent relationship for every PnP device.

    Debug mode only. The resulting CSV is intended for Precog's future
    "Devices by Connection" view. Each row keeps the child device identity
    together with DEVPKEY_Device_Parent so Precog can rebuild the hierarchy.

    Output:
        _PnpParentDevices.csv

    Columns:
        Class
        FriendlyName
        InstanceId
        ParentInstanceId
        Status
        Problem
        ConfigManagerErrorCode
    """
    path = out_dir / OUTPUT_FILES["PnP Parent Devices CSV"]
    ps_script = r"""
$rows = foreach ($device in (Get-PnpDevice -ErrorAction SilentlyContinue)) {
    $parentId = $null

    try {
        $parentProperty = Get-PnpDeviceProperty `
            -InstanceId $device.InstanceId `
            -KeyName 'DEVPKEY_Device_Parent' `
            -ErrorAction Stop

        if ($null -ne $parentProperty) {
            $parentId = [string]$parentProperty.Data
        }
    }
    catch {
        $parentId = $null
    }

    [PSCustomObject]@{
        Class                  = [string]$device.Class
        FriendlyName           = [string]$device.FriendlyName
        InstanceId             = [string]$device.InstanceId
        ParentInstanceId       = [string]$parentId
        Status                 = [string]$device.Status
        Problem                = [string]$device.Problem
        ConfigManagerErrorCode = [string]$device.ConfigManagerErrorCode
    }
}

$rows |
    Sort-Object Class,FriendlyName,InstanceId |
    ConvertTo-Csv -NoTypeInformation
"""
    ok, content = run_powershell(ps_script, timeout=300)

    if ok and not content.strip():
        content = (
            '"Class","FriendlyName","InstanceId","ParentInstanceId",'
            '"Status","Problem","ConfigManagerErrorCode"\n'
        )

    path.write_text(content or "", encoding="utf-8-sig", errors="replace")

    if not ok:
        return False, content or "PowerShell collection failed"

    if not path.exists() or path.stat().st_size == 0:
        return False, "Parent device CSV was not created"

    row_count = max(0, len([line for line in content.splitlines() if line.strip()]) - 1)
    return True, f"Collected parent relationship for {row_count} PnP devices"


def collect_pnp_device_status(out_dir: Path) -> Tuple[bool, str]:
    """Collect detailed Configuration Manager status for every PnP device.

    The JSON is pre-decoded for Precog:
    - ProblemCode / ProblemName
    - ProblemStatus as hexadecimal NTSTATUS
    - DevNodeStatus raw value and decoded DN_* flags
    - ConfigFlags raw value and decoded CONFIGFLAG_* flags
    - DriverLoaded / DeviceStarted convenience booleans
    """
    path = out_dir / OUTPUT_FILES["PnP Device Status JSON"]

    ps_script = r"""
$problemNames = @{
    0  = 'CM_PROB_NONE'
    1  = 'CM_PROB_NOT_CONFIGURED'
    2  = 'CM_PROB_DEVLOADER_FAILED'
    3  = 'CM_PROB_OUT_OF_MEMORY'
    4  = 'CM_PROB_ENTRY_IS_WRONG_TYPE'
    5  = 'CM_PROB_LACKED_ARBITRATOR'
    6  = 'CM_PROB_BOOT_CONFIG_CONFLICT'
    7  = 'CM_PROB_FAILED_FILTER'
    8  = 'CM_PROB_DEVLOADER_NOT_FOUND'
    9  = 'CM_PROB_INVALID_DATA'
    10 = 'CM_PROB_FAILED_START'
    11 = 'CM_PROB_LIAR'
    12 = 'CM_PROB_NORMAL_CONFLICT'
    13 = 'CM_PROB_NOT_VERIFIED'
    14 = 'CM_PROB_NEED_RESTART'
    15 = 'CM_PROB_REENUMERATION'
    16 = 'CM_PROB_PARTIAL_LOG_CONF'
    17 = 'CM_PROB_UNKNOWN_RESOURCE'
    18 = 'CM_PROB_REINSTALL'
    19 = 'CM_PROB_REGISTRY'
    20 = 'CM_PROB_VXDLDR'
    21 = 'CM_PROB_WILL_BE_REMOVED'
    22 = 'CM_PROB_DISABLED'
    23 = 'CM_PROB_DEVLOADER_NOT_READY'
    24 = 'CM_PROB_DEVICE_NOT_THERE'
    25 = 'CM_PROB_MOVED'
    26 = 'CM_PROB_TOO_EARLY'
    27 = 'CM_PROB_NO_VALID_LOG_CONF'
    28 = 'CM_PROB_FAILED_INSTALL'
    29 = 'CM_PROB_HARDWARE_DISABLED'
    30 = 'CM_PROB_CANT_SHARE_IRQ'
    31 = 'CM_PROB_FAILED_ADD'
    32 = 'CM_PROB_DISABLED_SERVICE'
    33 = 'CM_PROB_TRANSLATION_FAILED'
    34 = 'CM_PROB_NO_SOFTCONFIG'
    35 = 'CM_PROB_BIOS_TABLE'
    36 = 'CM_PROB_IRQ_TRANSLATION_FAILED'
    37 = 'CM_PROB_FAILED_DRIVER_ENTRY'
    38 = 'CM_PROB_DRIVER_FAILED_PRIOR_UNLOAD'
    39 = 'CM_PROB_DRIVER_FAILED_LOAD'
    40 = 'CM_PROB_DRIVER_SERVICE_KEY_INVALID'
    41 = 'CM_PROB_LEGACY_SERVICE_NO_DEVICES'
    42 = 'CM_PROB_DUPLICATE_DEVICE'
    43 = 'CM_PROB_FAILED_POST_START'
    44 = 'CM_PROB_HALTED'
    45 = 'CM_PROB_PHANTOM'
    46 = 'CM_PROB_SYSTEM_SHUTDOWN'
    47 = 'CM_PROB_HELD_FOR_EJECT'
    48 = 'CM_PROB_DRIVER_BLOCKED'
    49 = 'CM_PROB_REGISTRY_TOO_LARGE'
    50 = 'CM_PROB_SETPROPERTIES_FAILED'
    51 = 'CM_PROB_WAITING_ON_DEPENDENCY'
    52 = 'CM_PROB_UNSIGNED_DRIVER'
    53 = 'CM_PROB_USED_BY_DEBUGGER'
    54 = 'CM_PROB_DEVICE_RESET'
    55 = 'CM_PROB_CONSOLE_LOCKED'
    56 = 'CM_PROB_NEED_CLASS_CONFIG'
    57 = 'CM_PROB_GUEST_ASSIGNMENT_FAILED'
    58 = 'CM_PROB_FAILED_DRIVER_INTEGRITY_CHECK'
    59 = 'CM_PROB_INSUFFICIENT_POWER'
    60 = 'CM_PROB_FIRMWARE_RESOURCE_CONFLICT'
}

$dnFlags = [ordered]@{
    0x00000001 = 'DN_ROOT_ENUMERATED'
    0x00000002 = 'DN_DRIVER_LOADED'
    0x00000004 = 'DN_ENUM_LOADED'
    0x00000008 = 'DN_STARTED'
    0x00000010 = 'DN_MANUAL'
    0x00000020 = 'DN_NEED_TO_ENUM'
    0x00000040 = 'DN_NOT_FIRST_TIME'
    0x00000080 = 'DN_HARDWARE_ENUM'
    0x00000100 = 'DN_LIAR'
    0x00000200 = 'DN_HAS_MARK'
    0x00000400 = 'DN_HAS_PROBLEM'
    0x00000800 = 'DN_FILTERED'
    0x00001000 = 'DN_MOVED'
    0x00002000 = 'DN_DISABLEABLE'
    0x00004000 = 'DN_REMOVABLE'
    0x00008000 = 'DN_PRIVATE_PROBLEM'
    0x00010000 = 'DN_MF_PARENT'
    0x00020000 = 'DN_MF_CHILD'
    0x00040000 = 'DN_WILL_BE_REMOVED'
    0x00080000 = 'DN_NOT_FIRST_TIMEE'
    0x00100000 = 'DN_STOP_FREE_RES'
    0x00200000 = 'DN_REBAL_CANDIDATE'
    0x00400000 = 'DN_BAD_PARTIAL'
    0x00800000 = 'DN_NT_ENUMERATOR'
    0x01000000 = 'DN_NT_DRIVER'
    0x02000000 = 'DN_NEEDS_LOCKING'
    0x04000000 = 'DN_ARM_WAKEUP'
    0x08000000 = 'DN_APM_ENUMERATOR'
    0x10000000 = 'DN_APM_DRIVER'
    0x20000000 = 'DN_SILENT_INSTALL'
    0x40000000 = 'DN_NO_SHOW_IN_DM'
    0x80000000 = 'DN_BOOT_LOG_PROB'
}

$configFlags = [ordered]@{
    0x00000001 = 'CONFIGFLAG_DISABLED'
    0x00000002 = 'CONFIGFLAG_REMOVED'
    0x00000004 = 'CONFIGFLAG_MANUAL_INSTALL'
    0x00000008 = 'CONFIGFLAG_IGNORE_BOOT_LC'
    0x00000010 = 'CONFIGFLAG_NET_BOOT'
    0x00000020 = 'CONFIGFLAG_REINSTALL'
    0x00000040 = 'CONFIGFLAG_FAILEDINSTALL'
    0x00000080 = 'CONFIGFLAG_CANTSTOPACHILD'
    0x00000100 = 'CONFIGFLAG_OKREMOVEROM'
    0x00000200 = 'CONFIGFLAG_NOREMOVEEXIT'
    0x00000400 = 'CONFIGFLAG_FINISH_INSTALL'
    0x00000800 = 'CONFIGFLAG_NEEDS_FORCED_CONFIG'
    0x00001000 = 'CONFIGFLAG_NETBOOT_CARD'
    0x00002000 = 'CONFIGFLAG_PARTIAL_LOG_CONF'
    0x00004000 = 'CONFIGFLAG_SUPPRESS_SURPRISE'
    0x00008000 = 'CONFIGFLAG_VERIFY_HARDWARE'
    0x00010000 = 'CONFIGFLAG_FINISHINSTALL_UI'
    0x00020000 = 'CONFIGFLAG_FINISHINSTALL_ACTION'
    0x00040000 = 'CONFIGFLAG_BOOT_DEVICE'
}

function Get-PropertyValue {
    param(
        [object[]]$Properties,
        [string]$KeyName,
        $DefaultValue = $null
    )

    $match = $Properties | Where-Object { $_.KeyName -eq $KeyName } | Select-Object -First 1
    if ($null -eq $match -or $null -eq $match.Data) {
        return $DefaultValue
    }
    return $match.Data
}

function Convert-Flags {
    param(
        [UInt64]$Value,
        [System.Collections.IDictionary]$Map
    )

    $names = @()
    foreach ($entry in $Map.GetEnumerator()) {
        $mask = [UInt64]$entry.Key
        if (($Value -band $mask) -eq $mask) {
            $names += [string]$entry.Value
        }
    }
    return @($names)
}

$result = foreach ($device in (Get-PnpDevice -ErrorAction SilentlyContinue)) {
    $properties = @()
    try {
        $properties = @(Get-PnpDeviceProperty `
            -InstanceId $device.InstanceId `
            -KeyName @(
                'DEVPKEY_Device_ProblemCode',
                'DEVPKEY_Device_ProblemStatus',
                'DEVPKEY_Device_DevNodeStatus',
                'DEVPKEY_Device_ConfigFlags'
            ) `
            -ErrorAction SilentlyContinue)
    }
    catch {
        $properties = @()
    }

    $fallbackCode = 0
    if ($null -ne $device.ConfigManagerErrorCode) {
        $fallbackCode = [int]$device.ConfigManagerErrorCode
    }
    elseif ($null -ne $device.Problem) {
        try { $fallbackCode = [int]$device.Problem } catch { $fallbackCode = 0 }
    }

    $problemCodeRaw = Get-PropertyValue $properties 'DEVPKEY_Device_ProblemCode' $fallbackCode
    try { $problemCode = [int]$problemCodeRaw } catch { $problemCode = $fallbackCode }

    $problemStatusRaw = Get-PropertyValue $properties 'DEVPKEY_Device_ProblemStatus' 0
    try { $problemStatusUInt = [UInt32]$problemStatusRaw } catch { $problemStatusUInt = [UInt32]0 }

    $devNodeRaw = Get-PropertyValue $properties 'DEVPKEY_Device_DevNodeStatus' 0
    try { $devNodeStatus = [UInt32]$devNodeRaw } catch { $devNodeStatus = [UInt32]0 }

    $configRaw = Get-PropertyValue $properties 'DEVPKEY_Device_ConfigFlags' 0
    try { $configStatus = [UInt32]$configRaw } catch { $configStatus = [UInt32]0 }

    $problemName = if ($problemNames.ContainsKey($problemCode)) {
        $problemNames[$problemCode]
    }
    else {
        "CM_PROB_UNKNOWN_$problemCode"
    }

    [PSCustomObject]@{
        Class = $device.Class
        FriendlyName = $device.FriendlyName
        InstanceId = $device.InstanceId
        Status = [string]$device.Status
        Present = ($device.Status -ne 'Unknown')
        ProblemCode = $problemCode
        ProblemName = $problemName
        ProblemStatus = ('0x{0:X8}' -f $problemStatusUInt)
        ProblemStatusRaw = [UInt32]$problemStatusUInt
        DevNodeStatusRaw = [UInt32]$devNodeStatus
        DevNodeStatusHex = ('0x{0:X8}' -f $devNodeStatus)
        DevNodeFlags = @(Convert-Flags $devNodeStatus $dnFlags)
        ConfigFlagsRaw = [UInt32]$configStatus
        ConfigFlagsHex = ('0x{0:X8}' -f $configStatus)
        ConfigFlags = @(Convert-Flags $configStatus $configFlags)
        DriverLoaded = (($devNodeStatus -band 0x00000002) -ne 0)
        DeviceStarted = (($devNodeStatus -band 0x00000008) -ne 0)
    }
}

[ordered]@{
    SchemaVersion = 'Precog.PnpDeviceStatus.v1'
    GeneratedTime = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    DeviceCount = @($result).Count
    PresentDeviceCount = @($result | Where-Object { $_.Present -eq $true }).Count
    ProblemDeviceCount = @($result | Where-Object { $_.Present -eq $true -and $_.ProblemCode -ne 0 }).Count
    GhostDeviceCount = @($result | Where-Object { $_.Present -eq $false }).Count
    Devices = @($result | Sort-Object Class,FriendlyName,InstanceId)
} | ConvertTo-Json -Depth 8
"""
    ok, content = run_powershell(ps_script, timeout=600)

    try:
        if ok:
            json.loads(content)
            path.write_text(content, encoding="utf-8", errors="replace")
            return True, "OK"
        path.write_text(content or "", encoding="utf-8", errors="replace")
        return False, content
    except Exception as exc:
        path.write_text(f"[EXCEPTION] {exc}\n{content}", encoding="utf-8", errors="replace")
        return False, str(exc)


class CollectionProgressUI:
    """Compact Dowsing collection window. The run log remains the source of truth on disk."""

    def __init__(self, mode_name: str, total: int, output_dir: Path):
        self.root = None
        self.total = max(total, 1)
        self.finished = False
        if tk is None:
            return
        try:
            root = tk.Tk()
            self.root = root
            root.title("Dowsing - Collection")
            # Slightly taller default size so the footer is always visible on launch.
            root.geometry("720x560")
            root.minsize(680, 520)
            root.configure(bg="#f8fafc")
            root.protocol("WM_DELETE_WINDOW", self._on_close)

            root.update_idletasks()
            x = (root.winfo_screenwidth() - 720) // 2
            y = (root.winfo_screenheight() - 560) // 2
            root.geometry(f"720x560+{x}+{y}")

            header = tk.Frame(root, bg="#f8fafc")
            header.pack(fill="x", padx=28, pady=(22, 10))
            tk.Label(header, text="Dowsing", font=("Segoe UI", 22, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left")
            self.mode_label = tk.Label(header, text=mode_name, font=("Segoe UI", 9, "bold"), bg="#e2e8f0", fg="#334155", padx=10, pady=5)
            self.mode_label.pack(side="right", pady=4)

            card = tk.Frame(root, bg="#ffffff", highlightbackground="#cbd5e1", highlightthickness=1)
            card.pack(fill="x", padx=28, pady=(0, 12))
            self.step_label = tk.Label(card, text="Preparing collection...", anchor="w", font=("Segoe UI", 11, "bold"), bg="#ffffff", fg="#0f172a")
            self.step_label.pack(fill="x", padx=18, pady=(14, 3))
            self.count_label = tk.Label(card, text=f"0 / {total}", anchor="w", font=("Segoe UI", 9), bg="#ffffff", fg="#64748b")
            self.count_label.pack(fill="x", padx=18)
            self.progress = ttk.Progressbar(card, orient="horizontal", mode="determinate", maximum=self.total)
            self.progress.pack(fill="x", padx=18, pady=(7, 9))
            self.output_label = tk.Label(card, text=f"Output: {output_dir}", anchor="w", justify="left", wraplength=640, font=("Segoe UI", 8), bg="#ffffff", fg="#64748b")
            self.output_label.pack(fill="x", padx=18, pady=(0, 12))

            # Fixed footer is created before the expanding log area and packed at the
            # bottom. This guarantees that Close is visible without resizing.
            footer = tk.Frame(root, bg="#f8fafc")
            footer.pack(side="bottom", fill="x", padx=28, pady=(0, 16))
            self.status_label = tk.Label(footer, text="Collecting platform data...", anchor="w", font=("Segoe UI", 9), bg="#f8fafc", fg="#475569")
            self.status_label.pack(side="left", fill="x", expand=True)
            self.close_btn = tk.Button(
                footer,
                text="Close",
                command=self._on_close,
                font=("Segoe UI", 10, "bold"),
                bg="#0f172a",
                fg="#ffffff",
                activebackground="#334155",
                activeforeground="#ffffff",
                disabledforeground="#94a3b8",
                relief="flat",
                cursor="arrow",
                padx=18,
                pady=7,
                state="disabled",
            )
            self.close_btn.pack(side="right", padx=(14, 0))

            log_card = tk.Frame(root, bg="#0f172a")
            log_card.pack(fill="both", expand=True, padx=28, pady=(0, 12))
            tk.Label(log_card, text="Collection Log", anchor="w", font=("Segoe UI", 10, "bold"), bg="#0f172a", fg="#e2e8f0").pack(fill="x", padx=14, pady=(9, 4))
            self.log_text = tk.Text(log_card, height=10, wrap="word", font=("Consolas", 9), bg="#0f172a", fg="#cbd5e1", insertbackground="#ffffff", relief="flat", padx=10, pady=8)
            self.log_text.pack(fill="both", expand=True, padx=4, pady=(0, 4))
            self.log_text.configure(state="disabled")
            self._pump()
        except Exception:
            self.root = None

    def _on_close(self):
        """Close immediately after completion; explain why collection cannot be interrupted mid-step."""
        if self.root is None:
            return
        if self.finished:
            try:
                self.root.destroy()
            except Exception:
                pass
            return

        # Native X remains responsive and explains the current behavior instead of
        # silently ignoring the click as the previous implementation did.
        if messagebox is not None:
            try:
                messagebox.showinfo(
                    "Dowsing is collecting",
                    "Collection is still in progress.\n\n"
                    "Please wait for the current collection to finish before closing Dowsing.",
                    parent=self.root,
                )
            except Exception:
                pass

    def _pump(self):
        if self.root is not None:
            try:
                self.root.update_idletasks()
                self.root.update()
            except Exception:
                self.root = None

    def log(self, message: str):
        if self.root is None:
            return
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
            self._pump()
        except Exception:
            pass

    def start_step(self, current: int, item: str):
        if self.root is None:
            return
        self.step_label.configure(text=item)
        self.count_label.configure(text=f"{current} / {self.total}")
        self.progress["value"] = max(0, current - 1)
        self.status_label.configure(text="Collecting platform data...")
        self.log(f"[RUN] {item}")
        self._pump()

    def finish_step(self, current: int, item: str, ok: bool, detail: str):
        if self.root is None:
            return
        self.progress["value"] = current
        self.log(f"[OK] {item}" if ok else f"[FAIL] {item} ({detail})")
        self._pump()

    def finish(self, zip_path: Path | None, failed_count: int):
        if self.root is None:
            return
        self.finished = True
        self.progress["value"] = self.total
        self.step_label.configure(text="Collection complete")
        self.count_label.configure(text=f"{self.total} / {self.total}")
        if zip_path and zip_path.exists():
            self.status_label.configure(text=f"Done - {failed_count} failed. ZIP: {zip_path.name}" if failed_count else f"Done - ZIP: {zip_path.name}")
            self.log(f"[DONE] Zip file: {zip_path}")
        else:
            self.status_label.configure(text=f"Collection finished with {failed_count} failed item(s).")

        # The Close button is always present; completion only enables it.
        try:
            self.close_btn.configure(state="normal", cursor="hand2")
        except Exception:
            pass
        self._pump()
        try:
            self.root.mainloop()
        except Exception:
            pass

def console_available() -> bool:
    """Return True when a writable console stdout exists.

    PyInstaller --windowed/--noconsole sets sys.stdout/sys.stderr to None on
    Windows. Console output must therefore be treated as optional.
    """
    return sys.stdout is not None and hasattr(sys.stdout, "write")


def safe_print(*args, **kwargs) -> None:
    """Best-effort console print; no-op for windowed builds."""
    if not console_available():
        return
    try:
        print(*args, **kwargs)
    except Exception:
        pass


def print_progress(current: int, total: int, item: str) -> None:
    """Render one replaceable progress line when a console is available."""
    if not console_available():
        return

    message = f"[{current}/{total}] {item}"
    try:
        width = shutil.get_terminal_size(fallback=(100, 24)).columns
    except Exception:
        width = 100

    visible_width = max(20, width - 1)
    if len(message) > visible_width:
        message = message[: max(0, visible_width - 3)] + "..."

    try:
        sys.stdout.write("\r" + message.ljust(visible_width))
        sys.stdout.flush()
    except Exception:
        pass


def finish_progress(message: str) -> None:
    """Finish console progress when a console is available."""
    if not console_available():
        return

    try:
        width = shutil.get_terminal_size(fallback=(100, 24)).columns
    except Exception:
        width = 100
    visible_width = max(20, width - 1)

    try:
        sys.stdout.write("\r" + message[:visible_width].ljust(visible_width) + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def write_runlog(run_log_path: Path, lines: List[str]) -> None:
    run_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_collection_status(
    out_dir: Path,
    computer_name: str,
    timestamp_compact: str,
    statuses: Dict[str, str],
) -> None:
    path = out_dir / OUTPUT_FILES["Collection Status"]
    output_folder = str(out_dir.resolve())

    lines = [
        f"{APP_NAME} Python",
        f"ComputerName={computer_name}",
        f"Timestamp={timestamp_compact}",
        f"OutputFolder={output_folder}",
        f"KeepOutputFolderAfterZip={KEEP_OUTPUT_FOLDER_AFTER_ZIP}",
        "",
        "[Collection Status]",
    ]
    for key, value in statuses.items():
        lines.append(f"{key}={value}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def zip_output_folder(out_dir: Path) -> Path:
    zip_path = out_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in out_dir.rglob("*"):
            if file.is_file():
                zf.write(file, arcname=file.relative_to(out_dir))
    return zip_path


def normalize_status(ok: bool, detail: str) -> str:
    if ok:
        return "OK"
    if detail == "empty output":
        return "EMPTY"
    if detail == "timeout":
        return "TIMEOUT"
    if detail == "source not found":
        return "NOT_FOUND"
    return "FAIL"


def create_output_dir(base_dir: Path | None = None) -> Path:
    computer_name = socket.gethostname()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = base_dir or Path.cwd()
    out_dir = root / f"Driver_Logs_{computer_name}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def main() -> int:
    global MODE_NAME

    # Dowsing now has a dedicated GUI, so hide the legacy console window when possible.
    hide_console_window()

    mode = get_mode_from_args()
    if mode is None:
        mode = select_run_mode()
        if mode is None:
            safe_print("[INFO] Dowsing cancelled.")
            return 0
        remember_mode_for_elevation(mode)

    MODE_NAME = "Default (For Precog)" if mode == "default" else "Debug (Full Collection)"
    ensure_admin()

    computer_name = socket.gethostname()
    timestamp_compact = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = create_output_dir()
    run_log_path = out_dir / OUTPUT_FILES["Run Log"]

    collectors = build_collectors(mode)

    run_lines = [
        f"[OK] {APP_NAME} started",
        f"[OK] Mode: {MODE_NAME}",
        f"[OK] Collector count: {len(collectors)}",
        f"[OK] ComputerName: {computer_name}",
        f"[OK] Output folder: {out_dir}",
        f"[OK] KeepOutputFolderAfterZip: {KEEP_OUTPUT_FOLDER_AFTER_ZIP}",
        "[OK] Collecting logs, please wait...",
    ]

    statuses: Dict[str, str] = {}
    if mode == "default":
        statuses["PnP Device Status"] = "NOT_COLLECTED"
    total_collectors = len(collectors)
    progress_ui = CollectionProgressUI(MODE_NAME, total_collectors, out_dir)
    progress_ui.log(f"[OK] Mode: {MODE_NAME}")
    progress_ui.log(f"[OK] Collector count: {total_collectors}")
    if mode == "default":
        progress_ui.log("[SKIP] PnP Device Status (Debug only)")

    for current_index, (display_name, collector) in enumerate(collectors, start=1):
        print_progress(current_index, total_collectors, display_name)
        progress_ui.start_step(current_index, display_name)

        run_lines.append(f"[RUN] {display_name}")
        write_runlog(run_log_path, run_lines)

        ok, detail = collector(out_dir)
        status = normalize_status(ok, detail)
        statuses[display_name] = status

        if ok:
            run_lines.append(f"[OK] {display_name}")
        else:
            run_lines.append(f"[FAIL] {display_name} ({detail})")

        write_runlog(run_log_path, run_lines)
        progress_ui.finish_step(current_index, display_name, ok, detail)

    failed_count = sum(1 for value in statuses.values() if value not in {"OK", "NOT_COLLECTED"})
    finish_progress(
        f"[{total_collectors}/{total_collectors}] Log collection complete"
        + (f" ({failed_count} failed)" if failed_count else "")
    )

    statuses["Collection Status"] = "OK"
    statuses["Zip"] = "PENDING"
    write_collection_status(out_dir, computer_name, timestamp_compact, statuses)

    zip_path: Path | None = None
    try:
        zip_path = zip_output_folder(out_dir)
        statuses["Zip"] = "OK"
        run_lines.append("[OK] Compress Output Folder")
    except Exception as exc:
        statuses["Zip"] = "FAIL"
        run_lines.append(f"[FAIL] Compress Output Folder ({exc})")

    # Update status before the final zip rewrite so the zip contains Zip=OK/FAIL.
    write_collection_status(out_dir, computer_name, timestamp_compact, statuses)
    write_runlog(run_log_path, run_lines)

    if zip_path and zip_path.exists():
        zip_path = zip_output_folder(out_dir)
        run_lines.append("")
        run_lines.append(f"[DONE] Zip file: {zip_path}")

        if not KEEP_OUTPUT_FOLDER_AFTER_ZIP:
            try:
                shutil.rmtree(out_dir)
                run_lines.append(f"[OK] Removed output folder: {out_dir}")
            except Exception as exc:
                run_lines.append(f"[FAIL] Remove output folder ({exc})")
        else:
            run_lines.append(f"[DONE] Output folder: {out_dir}")
    else:
        run_lines.append("")
        run_lines.append(f"[DONE] Output folder: {out_dir}")

    # If the folder was removed, write the final run log into a small sidecar txt next to zip only when needed.
    if out_dir.exists():
        write_runlog(run_log_path, run_lines)
    elif zip_path:
        sidecar_log = zip_path.with_suffix(".RunLog.txt")
        sidecar_log.write_text("\n".join(run_lines) + "\n", encoding="utf-8")

    safe_print("=" * 60)
    if zip_path and zip_path.exists():
        safe_print(f"[DONE] Zip file: {zip_path}")
        if not KEEP_OUTPUT_FOLDER_AFTER_ZIP:
            safe_print("[DONE] Output folder removed; only ZIP is kept.")
    else:
        safe_print(f"[DONE] Output folder: {out_dir}")
    safe_print("=" * 60)

    progress_ui.finish(zip_path, failed_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
