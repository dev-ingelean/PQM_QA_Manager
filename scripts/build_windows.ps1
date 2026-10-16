$ErrorActionPreference = "Stop"
uv sync --extra dev
uv run pyinstaller --noconfirm --clean --windowed --name "PQM Quality Manager" --icon "src/pqm_quality_manager/static/app.ico" --paths src --add-data "src/pqm_quality_manager/static;pqm_quality_manager/static" main.py
Write-Host "Ejecutable generado en dist/PQM Quality Manager/"
