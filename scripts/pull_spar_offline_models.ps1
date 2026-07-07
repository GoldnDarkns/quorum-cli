# Pull Ollama models for SPAR offline presets (Windows).
# Usage:
#   powershell -File scripts/pull_spar_offline_models.ps1
#   powershell -File scripts/pull_spar_offline_models.ps1 -Preset thesis

param(
    [ValidateSet("uniform", "fast-thesis", "thesis")]
    [string]$Preset = "fast-thesis"
)

$ErrorActionPreference = "Stop"

$configPath = Join-Path $PSScriptRoot "..\config\spar_offline_models.json"
if (-not (Test-Path $configPath)) {
    Write-Error "Missing config: $configPath"
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$models = $config.pull_order.$Preset
if (-not $models) {
    Write-Error "Unknown preset: $Preset"
}

Write-Host "SPAR offline — pulling preset '$Preset' ($($models.Count) models)..."
Write-Host ""

foreach ($model in $models) {
    Write-Host ">>> ollama pull $model"
    ollama pull $model
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ollama pull failed for $model"
    }
}

Write-Host ""
Write-Host "Done. Run a pilot:"
Write-Host "  uv run python examples/spar_ollama_pilot.py --preset $Preset --scenario liberation-day"
