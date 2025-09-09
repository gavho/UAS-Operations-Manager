param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'

$libDir = Join-Path $ProjectRoot 'lib'
$backupDir = Join-Path $ProjectRoot ('lib_backup_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$tempDir = Join-Path $ProjectRoot ('_tmp_spatialite_' + [guid]::NewGuid().ToString())

Write-Host "Project root: $ProjectRoot"
Write-Host "Lib dir: $libDir"

# Backup existing lib
if (Test-Path $libDir) {
    Write-Host "Backing up existing lib to $backupDir"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    Copy-Item -Path (Join-Path $libDir '*') -Destination $backupDir -Recurse -Force -ErrorAction SilentlyContinue
}

# Create temp dir
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

# URLs for x64 builds (latest versions)
$downloads = @(
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/mod_spatialite-5.1.0-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/libspatialite-5.1.0-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/geos-3.12.0-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/proj-9.3.1-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/iconv-1.17-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/libxml2-2.11.5-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/freexl-2.0.0-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/zlib-1.3-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/xz-5.4.4-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/zstd-1.5.5-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/tiff-4.6.0-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/webp-1.3.2-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/openssl-3.1.4-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/curl-8.4.0-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/expat-2.5.0-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/readline-8.2-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/minizip-4.0.4-win-amd64.7z',
    'https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/sqlite-3.43.2-win-amd64.7z'
)

# Download archives
$archivePaths = @()
foreach ($url in $downloads) {
    $fileName = [IO.Path]::GetFileName($url)
    $destPath = Join-Path $tempDir $fileName
    Write-Host "Downloading $fileName..."
    try {
        Invoke-WebRequest -Uri $url -OutFile $destPath -UseBasicParsing
        $archivePaths += $destPath
    } catch {
        Write-Warning "Failed to download $url : $($_.Exception.Message)"
    }
}

# Find 7-Zip
$sevenZip = Join-Path ${env:ProgramFiles} '7-Zip\7z.exe'
if (-not (Test-Path $sevenZip)) {
    $sevenZip = Join-Path ${env:ProgramFiles(x86)} '7-Zip\7z.exe'
}
if (-not (Test-Path $sevenZip)) {
    Write-Host "7-Zip not found. Installing via winget..."
    try {
        winget install --id 7zip.7zip -e --accept-package-agreements --accept-source-agreements | Out-Null
    } catch {
        Write-Warning "winget install failed: $($_.Exception.Message)"
    }
    $sevenZip = Join-Path ${env:ProgramFiles} '7-Zip\7z.exe'
}

# Extract archives
$extractedDirs = @()
foreach ($archive in $archivePaths) {
    $extractDir = Join-Path $tempDir ([IO.Path]::GetFileNameWithoutExtension($archive))
    New-Item -ItemType Directory -Force -Path $extractDir | Out-Null

    $ext = [IO.Path]::GetExtension($archive).ToLowerInvariant()
    if ($ext -eq '.zip') {
        Write-Host "Extracting $([IO.Path]::GetFileName($archive))..."
        Expand-Archive -LiteralPath $archive -DestinationPath $extractDir -Force
        $extractedDirs += $extractDir
    } elseif ($ext -eq '.7z' -and (Test-Path $sevenZip)) {
        Write-Host "Extracting $([IO.Path]::GetFileName($archive))..."
        & $sevenZip x -y "-o$extractDir" $archive | Out-Null
        $extractedDirs += $extractDir
    } else {
        Write-Warning "Cannot extract $archive (unsupported format or no 7-Zip)"
    }
}

# Clean lib and copy DLLs
Write-Host "Cleaning lib directory..."
if (Test-Path $libDir) {
    Get-ChildItem -Path $libDir -File -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
} else {
    New-Item -ItemType Directory -Force -Path $libDir | Out-Null
}

Write-Host "Copying DLLs to lib..."
$copiedCount = 0
foreach ($dir in $extractedDirs) {
    Get-ChildItem -Path $dir -Recurse -Include *.dll -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item $_.FullName -Destination $libDir -Force
        $copiedCount++
    }
}
Write-Host "Copied $copiedCount DLLs to lib"

# Copy proj.db if found
$projDbFound = $false
foreach ($dir in $extractedDirs) {
    $projDb = Get-ChildItem -Path $dir -Recurse -Filter proj.db -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($projDb) {
        Copy-Item $projDb.FullName -Destination (Join-Path $libDir 'proj.db') -Force
        Write-Host "Copied proj.db from $($projDb.FullName)"
        $projDbFound = $true
        break
    }
}
if (-not $projDbFound) {
    Write-Warning "proj.db not found in downloaded archives"
}

# Cleanup temp
Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Download and setup complete. Running verification..."

# Run verification
& python scripts/check_dll_arch.py
& python SQLiteExtTest.py

Write-Host "Done."
