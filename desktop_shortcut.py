"""Cria uma vez o atalho na Área de Trabalho para o executável instalado."""

import base64
import os
import subprocess
import sys


def ensure_desktop_shortcut():
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return "Atalho disponível apenas no executável Windows."
    target = os.path.abspath(sys.executable)
    # Uma string literal PowerShell não executa caracteres especiais do caminho.
    quoted = target.replace("'", "''")
    script = """
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
if (-not $desktop) { throw 'Área de Trabalho indisponível' }
$link = Join-Path $desktop 'Converte MP3 Sem Limite Evaldo.lnk'
if (-not (Test-Path -LiteralPath $link)) {
  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($link)
  $shortcut.TargetPath = '%s'
  $shortcut.WorkingDirectory = Split-Path -Parent '%s'
  $shortcut.IconLocation = '%s,0'
  $shortcut.Description = 'Converte MP3 Sem Limite Evaldo'
  $shortcut.Save()
}
""" % (quoted, quoted, quoted)
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                             "-EncodedCommand", encoded], capture_output=True, text=True,
                            timeout=15)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Falha ao criar atalho.")
    return "Atalho criado na Área de Trabalho."
