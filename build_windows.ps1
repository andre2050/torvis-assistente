$ErrorActionPreference = 'Stop'
$Python = if (Get-Command py -ErrorAction SilentlyContinue) { @('py','-3.13') } else { @('python') }
function Py { & $Python[0] $Python[1..($Python.Length-1)] @args; if ($LASTEXITCODE -ne 0) { throw "O comando Python falhou" } }
Py -m pip install -r requirements.txt
Py -m pip install pyinstaller
Py -m compileall -q .
Py -m pip install pytest
Py -m pytest -q
Py -m PyInstaller --clean --noconfirm packaging/assistente_inteligente.spec
Write-Host "Compilação concluída: dist\TORVIS\TORVIS.exe"
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($iscc) { & $iscc.Source packaging\Assistente-Inteligente.iss; Write-Host "Instalador concluído: dist-installer" }
else { Write-Host "Inno Setup não encontrado; o executável está pronto. Instale o Inno Setup para criar o instalador do Assistente Inteligente." }
