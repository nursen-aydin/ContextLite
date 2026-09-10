$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Find-Python {
    $commands = @(
        @{ Name = "py"; Prefix = @("-3.11") },
        @{ Name = "py"; Prefix = @("-3") },
        @{ Name = "python"; Prefix = @() }
    )
    foreach ($candidate in $commands) {
        try {
            $command = Get-Command $candidate.Name -ErrorAction Stop
            & $command.Source @($candidate.Prefix) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
            continue
        }
    }
    return $null
}

Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $Python = Find-Python
    if ($null -eq $Python) {
        throw "Python 3.11 veya daha yeni bir sürüm bulunamadı. Önce https://www.python.org/downloads/windows/ adresinden Python kurun ve bu dosyayı yeniden çalıştırın."
    }
    Write-Host "Sanal ortam hazırlanıyor..." -ForegroundColor Cyan
    $command = Get-Command $Python.Name -ErrorAction Stop
    & $command.Source @($Python.Prefix) -m venv .venv
}

$ReadyMarker = Join-Path $ProjectRoot ".venv\.contextlite-ready"
if (-not (Test-Path -LiteralPath $ReadyMarker)) {
    Write-Host "Bağımlılıklar ve Microsoft Foundry Local kuruluyor..." -ForegroundColor Cyan
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Bağımlılık kurulumu başarısız oldu. Terminaldeki ilk kırmızı hatayı kontrol edin."
    }
    New-Item -ItemType File -Path $ReadyMarker -Force | Out-Null
}

Write-Host "ContextLite açılıyor: http://127.0.0.1:8124/app" -ForegroundColor Green
Write-Host "İlk Foundry isteğinde seçilen model bir kez indirilebilir." -ForegroundColor Yellow
& $VenvPython -m uvicorn src.main:app --host 127.0.0.1 --port 8124
