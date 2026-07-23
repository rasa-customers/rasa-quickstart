#!/usr/bin/env pwsh
#
# Rasa Quickstart bootstrap (Windows / PowerShell).
#
#   irm https://raw.githubusercontent.com/rasa-customers/rasa-quickstart/main/install.ps1 | iex
#
# With options (note the & { ... } wrapper needed when piping to iex):
#
#   & ([scriptblock]::Create((irm https://.../install.ps1))) -Ides claude,cursor my-agent
#
# Installs uv (if missing), downloads the delivered project (template/), starts
# a fresh git repo, and runs setup (venv + skills + a trained model).
#
# Set -DryRun (or $env:DRY_RUN) to print the plan without doing anything.

[CmdletBinding()]
param(
    [string[]]$Ides = @(),
    [string]$Provider = "",
    [switch]$Yes,
    [Parameter(Position = 0)][string]$Target = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Repo = if ($env:RASA_QUICKSTART_REPO) { $env:RASA_QUICKSTART_REPO } else { "rasa-customers/rasa-quickstart" }
$Ref = if ($env:RASA_QUICKSTART_REF) { $env:RASA_QUICKSTART_REF } else { "main" }
if ($env:DRY_RUN) { $DryRun = $true }

if (-not $Target) { $Target = "rasa-quickstart" }

$setupArgs = ""
if ($Ides.Count -gt 0) { $setupArgs += " --ides " + ($Ides -join ",") }
if ($Provider) { $setupArgs += " --provider $Provider" }
if ($Yes) { $setupArgs += " --yes" }

$tarball = "https://github.com/$Repo/archive/refs/heads/$Ref.tar.gz"

function Write-Plan($msg) { Write-Output "PLAN: $msg" }

function Initialize-Uv {
    if ($DryRun) { Write-Plan "ensure uv is installed"; return }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Output "Installing uv..."
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    }
}

function Get-ProjectTemplate {
    if ($DryRun) {
        Write-Plan "fetch $tarball"
        Write-Plan "extract template/ into $Target"
        return
    }
    if ((Test-Path $Target) -and (Get-ChildItem -Force $Target | Select-Object -First 1)) {
        throw "Error: '$Target' already exists and is not empty."
    }
    $tmp = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString()))
    try {
        Write-Output "Downloading project..."
        $archive = Join-Path $tmp "rq.tar.gz"
        Invoke-WebRequest -Uri $tarball -OutFile $archive
        tar -xz -f $archive -C $tmp
        New-Item -ItemType Directory -Force -Path $Target | Out-Null
        $inner = Get-ChildItem -Directory $tmp |
            Where-Object { Test-Path (Join-Path $_.FullName "template") } |
            Select-Object -First 1
        Copy-Item -Recurse -Force (Join-Path $inner.FullName "template/*") $Target
    }
    finally {
        Remove-Item -Recurse -Force $tmp
    }
}

function Initialize-GitRepo {
    if ($DryRun) { Write-Plan "git init in $Target"; return }
    Push-Location $Target
    try { git init -q } finally { Pop-Location }
}

function Invoke-Setup {
    if ($DryRun) { Write-Plan "(cd $Target) uv run python scripts/setup.py$setupArgs"; return }
    Push-Location $Target
    try { Invoke-Expression "uv run python scripts/setup.py$setupArgs" } finally { Pop-Location }
}

Initialize-Uv
Get-ProjectTemplate
Initialize-GitRepo
Invoke-Setup

if (-not $DryRun) {
    Write-Output ""
    Write-Output "Done. Next:"
    Write-Output "  cd $Target"
    Write-Output "  # add RASA_LICENSE and your LLM key to .env, then:"
    Write-Output "  make inspect"
}
