$ErrorActionPreference = "Stop"
uv sync --extra dev
uv run pyinstaller --noconfirm --clean --windowed --name "PQM Quality Manager" --paths src main.py
Write-Host "Ejecutable generado en dist/PQM Quality Manager/"
