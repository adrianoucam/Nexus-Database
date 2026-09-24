@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
if defined NEXUSDB_BACKUP_PYTHON (
  "%NEXUSDB_BACKUP_PYTHON%" "%~dp0nexus_backup.py" %*
  exit /b
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0nexus_backup.py" %*
  exit /b
)
echo Configure NEXUSDB_BACKUP_PYTHON com o caminho do Python 3.10 ou superior.
exit /b 1
