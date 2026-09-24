@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "BUILD_PROFILE=%~1"
if not defined BUILD_PROFILE set "BUILD_PROFILE=debug"
where cargo >nul 2>&1
if errorlevel 1 (echo ERRO: cargo nao foi encontrado no PATH. Execute rustinstall.bat primeiro.& exit /b 1)
if /I "%BUILD_PROFILE%"=="debug" (cargo build) else if /I "%BUILD_PROFILE%"=="release" (cargo build --release) else (echo Uso: %~nx0 [debug^|release]& exit /b 2)
if errorlevel 1 (echo ERRO: a compilacao %BUILD_PROFILE% falhou.& exit /b 1)
echo Build %BUILD_PROFILE% concluido com sucesso.
exit /b 0
