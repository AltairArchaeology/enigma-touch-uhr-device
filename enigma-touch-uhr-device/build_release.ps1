[CmdletBinding()]
param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$Python = if ($Python) { $Python } else { Join-Path $root ".build-venv\Scripts\python.exe" }
$pythonPath = (Resolve-Path -LiteralPath $Python).Path
$workRoot = Join-Path $root ".build-release"
$stageRoot = Join-Path $root ".release-build"

Set-Location -LiteralPath $root
$version = (& $pythonPath -B -c "from enigma_uhr_touch.version import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) {
    throw "Could not read the application version."
}
$releaseRoot = Join-Path $root "release\v$version"

foreach ($path in @($workRoot, $stageRoot, $releaseRoot)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null

& $pythonPath -B -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Automated tests failed." }

& $pythonPath -B Enigma_Uhr_UI.py --smoke-test
if ($LASTEXITCODE -ne 0) { throw "Lite source smoke test failed." }

& $pythonPath -B Enigma_Uhr_Qt.pyw --smoke-test
if ($LASTEXITCODE -ne 0) { throw "Qt source smoke test failed." }

& $pythonPath -B -m PyInstaller --noconfirm --distpath $stageRoot --workpath (Join-Path $workRoot "lite") EnigmaTouchUhrLitePortable.spec
if ($LASTEXITCODE -ne 0) { throw "Lite build failed." }

& $pythonPath -B -m PyInstaller --noconfirm --distpath $stageRoot --workpath (Join-Path $workRoot "qt") EnigmaTouchUhrPortable.spec
if ($LASTEXITCODE -ne 0) { throw "Qt build failed." }

$artifacts = @(
    (Join-Path $stageRoot "Enigma Touch - Uhr Device.exe"),
    (Join-Path $stageRoot "EnigmaTouchUhrPortable.exe")
)
foreach ($artifact in $artifacts) {
    $process = Start-Process -FilePath $artifact -ArgumentList "--smoke-test" -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Packaged smoke test failed for $artifact."
    }
    Copy-Item -LiteralPath $artifact -Destination $releaseRoot -Force
}

$checksumLines = foreach ($artifact in Get-ChildItem -LiteralPath $releaseRoot -Filter "*.exe" | Sort-Object Name) {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifact.FullName).Hash.ToLowerInvariant()
    "$hash  $($artifact.Name)"
}
$checksumLines | Set-Content -LiteralPath (Join-Path $releaseRoot "SHA256SUMS.txt") -Encoding ascii

Write-Host "Release v$version created at $releaseRoot"
