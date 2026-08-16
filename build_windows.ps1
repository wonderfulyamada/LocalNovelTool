$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$deployCommand = Join-Path $projectRoot ".venv\Scripts\pyside6-deploy.exe"
$configFile = Join-Path $projectRoot "pysidedeploy.spec"
$builtApp = Join-Path $projectRoot "build\LocalNovelTool.dist"
$distribution = Join-Path $projectRoot "dist\LocalNovelTool"
$zipPath = Join-Path $projectRoot "dist\LocalNovelTool_v0.2.1.zip"

if (-not (Test-Path -LiteralPath $deployCommand -PathType Leaf)) {
    throw "pyside6-deploy was not found. Install requirements-dev.txt first."
}

if (Test-Path -LiteralPath $builtApp) {
    Remove-Item -LiteralPath $builtApp -Recurse -Force
}
& $deployCommand -c $configFile -f
$deployExitCode = $LASTEXITCODE

# pyside6-deploy writes the active interpreter as an absolute path. Keep the
# checked-in build configuration portable after every build.
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$configText = Get-Content -LiteralPath $configFile -Raw
$configText = $configText.Replace($venvPython, ".venv/Scripts/python.exe")
Set-Content -LiteralPath $configFile -Value $configText -Encoding ASCII

if ($deployExitCode -ne 0) {
    throw "pyside6-deploy failed."
}

if (-not (Test-Path -LiteralPath $builtApp -PathType Container)) {
    throw "Standalone build directory was not found: $builtApp"
}
$builtExe = Join-Path $builtApp "main.exe"
if (-not (Test-Path -LiteralPath $builtExe -PathType Leaf)) {
    throw "Built executable was not found: $builtExe"
}

if (Test-Path -LiteralPath $distribution) {
    Remove-Item -LiteralPath $distribution -Recurse -Force
}
New-Item -ItemType Directory -Path $distribution -Force | Out-Null
Copy-Item -Path (Join-Path $builtApp "*") -Destination $distribution -Recurse -Force
Rename-Item -LiteralPath (Join-Path $distribution "main.exe") -NewName "LocalNovelTool.exe"
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $distribution
Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE.txt") -Destination $distribution
Copy-Item -LiteralPath (Join-Path $projectRoot "THIRD_PARTY_LICENSES.txt") -Destination $distribution
Copy-Item -LiteralPath (Join-Path $projectRoot "CREDITS.txt") -Destination $distribution
Copy-Item -LiteralPath (Join-Path $projectRoot "licenses") -Destination $distribution -Recurse
$distributionResources = Join-Path $distribution "resources"
New-Item -ItemType Directory -Path $distributionResources -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot "build_assets\app.ico") -Destination (Join-Path $distributionResources "app.ico")

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -LiteralPath $distribution -DestinationPath $zipPath -CompressionLevel Optimal
