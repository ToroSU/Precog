import ctypes
import json
import shutil
import socket
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple


APP_NAME = "Dowsing"
MODE_NAME = "For Precog"
KEEP_OUTPUT_FOLDER_AFTER_ZIP = False  # False = only keep the .zip file if compression succeeds.

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
    "SetupAPI Device Log": "_SetupAPI.dev.log",
    "SetupAPI App Log": "_SetupAPI.app.log",
    "PowerCfg Available Sleep States": "_PowerCfg_A.txt",
    "PowerCfg Requests": "_PowerCfg_Requests.txt",
    "PowerCfg LastWake": "_PowerCfg_LastWake.txt",
    "PowerCfg Wake Armed": "_PowerCfg_WakeArmed.txt",
    "SleepStudy Report": "_SleepStudy.html",
    "Energy Report": "_EnergyReport.html",
    "Display Audio Camera System CSV": "_Display_Audio_Camera_System.csv",
    "USB TypeC UCSI CSV": "_USB_TypeC_UCSI.csv",
    "Vendor Related Devices CSV": "_Vendor_Related_Devices.csv",
    "EventLog System": "_EventLog_System.evtx",
    "EventLog Application": "_EventLog_Application.evtx",
    "EventLog Kernel PnP Configuration": "_EventLog_KernelPnP_Configuration.evtx",
    "EventLog DriverFrameworks UserMode": "_EventLog_DriverFrameworks_UserMode.evtx",
    "Collection Status": "_CollectionStatus.txt",
    "Run Log": "_RunLog.txt",
}


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
        print("[INFO] Administrator privilege required. Requesting elevation...")
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
        subprocess.run(cmd, timeout=timeout, check=True)
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


def collect_setupapi_dev_log(out_dir: Path) -> Tuple[bool, str]:
    return copy_file(Path(r"C:\Windows\INF\setupapi.dev.log"), out_dir / OUTPUT_FILES["SetupAPI Device Log"])


def collect_setupapi_app_log(out_dir: Path) -> Tuple[bool, str]:
    return copy_file(Path(r"C:\Windows\INF\setupapi.app.log"), out_dir / OUTPUT_FILES["SetupAPI App Log"])


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
    ensure_admin()

    computer_name = socket.gethostname()
    timestamp_compact = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = create_output_dir()
    run_log_path = out_dir / OUTPUT_FILES["Run Log"]

    collectors: List[Tuple[str, Callable[[Path], Tuple[bool, str]]]] = [
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
        ("MSInfo32", collect_msinfo32),
        ("DXDiag", collect_dxdiag),
        ("Catalog Map", collect_catalog_map),
        ("System Summary JSON", collect_system_summary),
        ("SetupAPI Device Log", collect_setupapi_dev_log),
        ("SetupAPI App Log", collect_setupapi_app_log),
        ("PowerCfg Available Sleep States", collect_powercfg_a),
        ("PowerCfg Requests", collect_powercfg_requests),
        ("PowerCfg LastWake", collect_powercfg_lastwake),
        ("PowerCfg Wake Armed", collect_powercfg_wake_armed),
        ("SleepStudy Report", collect_sleepstudy),
        ("Energy Report", collect_energy_report),
        ("Special Device Groups", collect_special_devices),
        ("Event Logs", collect_event_logs),
    ]

    run_lines = [
        f"[OK] {APP_NAME} started",
        f"[OK] Mode: {MODE_NAME}",
        f"[OK] ComputerName: {computer_name}",
        f"[OK] Output folder: {out_dir}",
        f"[OK] KeepOutputFolderAfterZip: {KEEP_OUTPUT_FOLDER_AFTER_ZIP}",
        "[OK] Collecting logs, please wait...",
    ]

    statuses: Dict[str, str] = {}

    for display_name, collector in collectors:
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

    print("=" * 60)
    if zip_path and zip_path.exists():
        print(f"[DONE] Zip file: {zip_path}")
        if not KEEP_OUTPUT_FOLDER_AFTER_ZIP:
            print("[DONE] Output folder removed; only ZIP is kept.")
    else:
        print(f"[DONE] Output folder: {out_dir}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
