# Run this from the frontend/ directory: .\create_dirs.ps1
# Creates all subdirectories and removes Vite's default boilerplate files.

$dirs = @(
    "src/api",
    "src/config",
    "src/hooks",
    "src/styles",
    "src/components/layout",
    "src/components/common",
    "src/pages",
    "src/sections"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host "  created  $dir"
}

# Remove Vite boilerplate files we don't need
$remove = @("src/App.css", "src/index.css", "public/vite.svg", "src/assets/react.svg")
foreach ($f in $remove) {
    if (Test-Path $f) {
        Remove-Item -Force -Path $f
        Write-Host "  removed  $f"
    }
}

Write-Host ""
Write-Host "Done. Now paste in the M1 files."
