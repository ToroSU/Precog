param(
    [string]$OutputRoot = $(if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path })
)

$ErrorActionPreference = 'Stop'

function Write-Status {
    param(
        [string]$Level,
        [string]$Message
    )
    $line = ('[{0}] {1}' -f $Level.ToUpper().PadRight(4), $Message)
    Write-Host $line
    Add-Content -Path $script:RunLogPath -Value $line -Encoding UTF8
}

function Set-StepStatus {
    param(
        [string]$Name,
        [string]$Status
    )
    $script:Status[$Name] = $Status
}

function Test-NonEmptyFile {
    param([string]$Path)
    return (Test-Path -LiteralPath $Path -PathType Leaf) -and ((Get-Item -LiteralPath $Path).Length -gt 0)
}

function Invoke-Collector {
    param(
        [string]$Name,
        [scriptblock]$Action,
        [string]$OutputFile = $null,
        [switch]$Optional
    )

    Write-Status 'RUN' $Name
    try {
        & $Action

        if ($OutputFile) {
            if (Test-Path -LiteralPath $OutputFile -PathType Leaf) {
                $fileInfo = Get-Item -LiteralPath $OutputFile
                if ($fileInfo.Length -gt 0) {
                    Set-StepStatus -Name $Name -Status 'OK'
                    Write-Status 'OK' $Name
                } else {
                    Set-StepStatus -Name $Name -Status 'EMPTY'
                    Write-Status 'EMPTY' "$Name (empty file)"
                }
            } else {
                Set-StepStatus -Name $Name -Status $(if ($Optional) { 'NOT_FOUND' } else { 'FAIL' })
                Write-Status $(if ($Optional) { 'NOTF' } else { 'FAIL' }) "$Name (output not found)"
            }
        } else {
            Set-StepStatus -Name $Name -Status 'OK'
            Write-Status 'OK' $Name
        }
    }
    catch {
        $status = if ($Optional) { 'FAIL' } else { 'FAIL' }
        Set-StepStatus -Name $Name -Status $status
        Write-Status 'FAIL' ("{0} - {1}" -f $Name, $_.Exception.Message)
    }
}

function Export-SystemSummaryJson {
    param([string]$Path)

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

    $obj | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Export-CatalogMapCsv {
    param([string]$Path)

    $drivers = Get-WindowsDriver -Online |
        Select-Object Driver, OriginalFileName, CatalogFile, ClassName, ProviderName, Date, Version

    if (-not $drivers) {
        throw 'Get-WindowsDriver returned no data.'
    }

    $drivers | Export-Csv -LiteralPath $Path -NoTypeInformation -Encoding UTF8
}

# Admin check
$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    Write-Host '[FAIL] Please run this script as Administrator.' -ForegroundColor Red
    exit 1
}

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$outputFolder = Join-Path -Path $OutputRoot -ChildPath ("Driver_Logs_{0}_{1}" -f $env:COMPUTERNAME, $timestamp)
New-Item -Path $outputFolder -ItemType Directory -Force | Out-Null

$script:RunLogPath = Join-Path $outputFolder '_RunLog.txt'
$collectionStatusPath = Join-Path $outputFolder '_CollectionStatus.txt'
$script:Status = [ordered]@{
    'OS Version' = 'PENDING'
    'SystemInfo' = 'PENDING'
    'Windows Version Reg' = 'PENDING'
    'BCD Info' = 'PENDING'
    'DISM Driver Info' = 'PENDING'
    'PnP Devices Info' = 'PENDING'
    'PnP Problem Devices' = 'PENDING'
    'Driver Query' = 'PENDING'
    'MSInfo32' = 'PENDING'
    'Catalog Map' = 'PENDING'
    'System Summary JSON' = 'PENDING'
    'SetupAPI Device Log' = 'PENDING'
    'Zip' = 'PENDING'
}

Set-Content -LiteralPath $script:RunLogPath -Value ("SystemInfoRecoder PowerShell started at {0}" -f (Get-Date)) -Encoding UTF8
Write-Status 'OK' 'Collecting logs, please wait...'

# Core files for CheckCheck.html compatibility
Invoke-Collector -Name 'OS Version' -OutputFile (Join-Path $outputFolder '_OSVersion.txt') -Action {
    cmd /c ver | Out-File -LiteralPath (Join-Path $outputFolder '_OSVersion.txt') -Encoding utf8
}

Invoke-Collector -Name 'SystemInfo' -OutputFile (Join-Path $outputFolder '_SystemInfo.txt') -Action {
    systeminfo | Out-File -LiteralPath (Join-Path $outputFolder '_SystemInfo.txt') -Encoding utf8
}

Invoke-Collector -Name 'Windows Version Reg' -OutputFile (Join-Path $outputFolder '_WindowsVersionReg.txt') -Action {
    reg query 'HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion' | Out-File -LiteralPath (Join-Path $outputFolder '_WindowsVersionReg.txt') -Encoding utf8
}

Invoke-Collector -Name 'BCD Info' -OutputFile (Join-Path $outputFolder '_BCDInfo.txt') -Action {
    bcdedit /enum all | Out-File -LiteralPath (Join-Path $outputFolder '_BCDInfo.txt') -Encoding utf8
}

Invoke-Collector -Name 'DISM Driver Info' -OutputFile (Join-Path $outputFolder '_Dism_DriverInfo.txt') -Action {
    dism /online /get-drivers /format:table | Out-File -LiteralPath (Join-Path $outputFolder '_Dism_DriverInfo.txt') -Encoding utf8
}

Invoke-Collector -Name 'PnP Devices Info' -OutputFile (Join-Path $outputFolder '_PnpDeviceInfo.txt') -Action {
    pnputil /enum-devices /drivers /ids | Out-File -LiteralPath (Join-Path $outputFolder '_PnpDeviceInfo.txt') -Encoding utf8
}

Invoke-Collector -Name 'PnP Problem Devices' -OutputFile (Join-Path $outputFolder '_PnpProblemDevices.txt') -Action {
    pnputil /enum-devices /problem | Out-File -LiteralPath (Join-Path $outputFolder '_PnpProblemDevices.txt') -Encoding utf8
}

Invoke-Collector -Name 'Driver Query' -OutputFile (Join-Path $outputFolder '_DriverQuery.txt') -Action {
    driverquery /v | Out-File -LiteralPath (Join-Path $outputFolder '_DriverQuery.txt') -Encoding utf8
}

Invoke-Collector -Name 'MSInfo32' -OutputFile (Join-Path $outputFolder '_SysInfo.txt') -Action {
    $target = Join-Path $outputFolder '_SysInfo.txt'
    Start-Process -FilePath msinfo32.exe -ArgumentList "/report `"$target`"" -WindowStyle Hidden -Wait
}

Invoke-Collector -Name 'Catalog Map' -OutputFile (Join-Path $outputFolder '_CatalogMap.csv') -Optional -Action {
    Export-CatalogMapCsv -Path (Join-Path $outputFolder '_CatalogMap.csv')
}

Invoke-Collector -Name 'System Summary JSON' -OutputFile (Join-Path $outputFolder '_SystemSummary.json') -Optional -Action {
    Export-SystemSummaryJson -Path (Join-Path $outputFolder '_SystemSummary.json')
}

$setupApiSource = Join-Path $env:windir 'INF\setupapi.dev.log'
if (Test-Path -LiteralPath $setupApiSource) {
    Invoke-Collector -Name 'SetupAPI Device Log' -OutputFile (Join-Path $outputFolder '_SetupAPI.dev.log') -Action {
        Copy-Item -LiteralPath $setupApiSource -Destination (Join-Path $outputFolder '_SetupAPI.dev.log') -Force
    }
} else {
    Set-StepStatus -Name 'SetupAPI Device Log' -Status 'NOT_FOUND'
    Write-Status 'NOTF' 'SetupAPI Device Log (source not found)'
}

# Status file
$statusLines = @(
    'SystemInfoRecoder PowerShell'
    ('ComputerName={0}' -f $env:COMPUTERNAME)
    ('Timestamp={0}' -f $timestamp)
    ('OutputFolder={0}' -f $outputFolder)
    ''
    '[Collection Status]'
)
$statusLines += $script:Status.GetEnumerator() | ForEach-Object { '{0}={1}' -f $_.Key, $_.Value }
Set-Content -LiteralPath $collectionStatusPath -Value $statusLines -Encoding UTF8

# Zip
$zipPath = "$outputFolder.zip"
try {
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $outputFolder '*') -DestinationPath $zipPath -Force
    if (Test-NonEmptyFile -Path $zipPath) {
        Set-StepStatus -Name 'Zip' -Status 'OK'
        Write-Status 'OK' 'Compress Output Folder'
    } else {
        Set-StepStatus -Name 'Zip' -Status 'FAIL'
        Write-Status 'FAIL' 'Compress Output Folder (zip not created)'
    }
}
catch {
    Set-StepStatus -Name 'Zip' -Status 'FAIL'
    Write-Status 'FAIL' ("Compress Output Folder - {0}" -f $_.Exception.Message)
}

# Rewrite final status file including Zip
$statusLines = @(
    'SystemInfoRecoder PowerShell'
    ('ComputerName={0}' -f $env:COMPUTERNAME)
    ('Timestamp={0}' -f $timestamp)
    ('OutputFolder={0}' -f $outputFolder)
    ''
    '[Collection Status]'
)
$statusLines += $script:Status.GetEnumerator() | ForEach-Object { '{0}={1}' -f $_.Key, $_.Value }
Set-Content -LiteralPath $collectionStatusPath -Value $statusLines -Encoding UTF8

Write-Host ''
Write-Host '============================================================'
Write-Host ('[DONE] Output folder: {0}' -f $outputFolder)
if (Test-NonEmptyFile -Path $zipPath) {
    Write-Host ('[DONE] Zip file:      {0}' -f $zipPath)
} else {
    Write-Host '[WARN] Zip file was not created. Please send the whole folder.'
}
Write-Host '============================================================'
