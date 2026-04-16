import ctypes
import csv
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

OUTPUT_FILES = {
    "OS Version": "_OSVersion.txt",
    "SystemInfo": "_SystemInfo.txt",
    "Windows Version Reg": "_WindowsVersionReg.txt",
    "BCD Info": "_BCDInfo.txt",
    "DISM Driver Info": "_Dism_DriverInfo.txt",
    "PnP Devices Info": "_PnpDeviceInfo.txt",
    "PnP Problem Devices": "_PnpProblemDevices.txt",
    "Driver Query": "_DriverQuery.txt",
    "MSInfo32 Report": "_SysInfo.txt",
    "Catalog Map": "_CatalogMap.csv",
    "System Summary JSON": "_SystemSummary.json",
    "SetupAPI Device Log": "_SetupAPI.dev.log",
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


def run_msinfo32(output_path: Path, timeout: int = 180) -> Tuple[bool, str]:
    try:
        subprocess.run(
            ["msinfo32.exe", "/report", str(output_path)],
            timeout=timeout,
            check=True,
        )
        if output_path.exists() and output_path.stat().st_size > 0:
            return True, "OK"
        return False, "empty output"
    except subprocess.TimeoutExpired:
        output_path.write_text("[TIMEOUT]", encoding="utf-8")
        return False, "timeout"
    except Exception as exc:
        output_path.write_text(f"[EXCEPTION] {exc}", encoding="utf-8")
        return False, str(exc)


def collect_os_version(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["OS Version"]
    return run_command(["cmd", "/c", "ver"], path)


def collect_systeminfo(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["SystemInfo"]
    return run_command(["systeminfo"], path, timeout=180)


def collect_windows_version_reg(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["Windows Version Reg"]
    return run_command(
        ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion"],
        path,
    )


def collect_bcdinfo(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["BCD Info"]
    return run_command(["bcdedit", "/enum", "all"], path)


def collect_dism_driverinfo(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["DISM Driver Info"]
    return run_command(
        ["dism", "/online", "/get-drivers", "/format:table"],
        path,
        timeout=180,
    )


def collect_pnp_devices(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["PnP Devices Info"]
    return run_command(
        ["pnputil", "/enum-devices", "/drivers", "/ids"],
        path,
        timeout=180,
    )


def collect_pnp_problem_devices(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["PnP Problem Devices"]
    return run_command(
        ["pnputil", "/enum-devices", "/problem"],
        path,
        timeout=120,
    )


def collect_driver_query(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["Driver Query"]
    return run_command(["driverquery", "/v"], path, timeout=180)


def collect_msinfo32(out_dir: Path) -> Tuple[bool, str]:
    path = out_dir / OUTPUT_FILES["MSInfo32 Report"]
    return run_msinfo32(path, timeout=240)


def collect_catalog_map(out_dir: Path) -> Tuple[bool, str]:
    """
    Align with your old PS1:
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

    if not ok:
        path.write_text(content or "", encoding="utf-8", errors="replace")
        return False, content

    try:
        path.write_text(content, encoding="utf-8-sig", errors="replace")
        if not path.exists() or path.stat().st_size == 0:
            return False, "empty output"
        return True, "OK"
    except Exception as exc:
        path.write_text(f"[EXCEPTION] {exc}", encoding="utf-8")
        return False, str(exc)


def collect_system_summary(out_dir: Path) -> Tuple[bool, str]:
    """
    Align with your old PS1 Export-SystemSummaryJson.
    """
    path = out_dir / OUTPUT_FILES["System Summary JSON"]

    ps_script = r"""
$computer = Get-CimInstance -ClassName Win32_ComputerSystem
$bios = Get-CimInstance -ClassName Win32_BIOS
$os = Get-CimInstance -ClassName Win32_OperatingSystem

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
    BIOSVersion = (($bios.SMBIOSBIOSVersion, $bios.Version -ne $null) | ForEach-Object { $_ }) -join ' | '
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

    if not ok:
        path.write_text(content or "", encoding="utf-8", errors="replace")
        return False, content

    try:
        json.loads(content)
        path.write_text(content, encoding="utf-8", errors="replace")
        return True, "OK"
    except Exception as exc:
        path.write_text(f"[EXCEPTION] {exc}\n{content}", encoding="utf-8", errors="replace")
        return False, str(exc)


def collect_setupapi_log(out_dir: Path) -> Tuple[bool, str]:
    src = Path(r"C:\Windows\INF\setupapi.dev.log")
    dst = out_dir / OUTPUT_FILES["SetupAPI Device Log"]

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
        ("PnP Problem Devices", collect_pnp_problem_devices),
        ("Driver Query", collect_driver_query),
        ("MSInfo32", collect_msinfo32),
        ("Catalog Map", collect_catalog_map),
        ("System Summary JSON", collect_system_summary),
        ("SetupAPI Device Log", collect_setupapi_log),
    ]

    run_lines = [
        f"[OK] {APP_NAME} started",
        f"[OK] Mode: {MODE_NAME}",
        f"[OK] ComputerName: {computer_name}",
        f"[OK] Output folder: {out_dir}",
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
    write_collection_status(out_dir, computer_name, timestamp_compact, statuses)

    try:
        zip_path = zip_output_folder(out_dir)
        statuses["Zip"] = "OK"
        run_lines.append("[OK] Compress Output Folder")
        run_lines.append("")
        run_lines.append(f"[DONE] Output folder: {out_dir}")
        run_lines.append(f"[DONE] Zip file: {zip_path}")
    except Exception as exc:
        statuses["Zip"] = "FAIL"
        run_lines.append(f"[FAIL] Compress Output Folder ({exc})")
        run_lines.append("")
        run_lines.append(f"[DONE] Output folder: {out_dir}")

    write_collection_status(out_dir, computer_name, timestamp_compact, statuses)
    write_runlog(run_log_path, run_lines)

    print("=" * 60)
    print(f"[DONE] Output folder: {out_dir}")
    zip_candidate = out_dir.with_suffix(".zip")
    if zip_candidate.exists():
        print(f"[DONE] Zip file: {zip_candidate}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())