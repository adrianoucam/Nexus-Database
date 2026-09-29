@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "BUILD_PROFILE=%~1"
if not defined BUILD_PROFILE set "BUILD_PROFILE=debug"
set "BUILD_BACKEND=%~2"
if not defined BUILD_BACKEND set "BUILD_BACKEND=cpu"
if not "%~3"=="" goto usage
if /I not "%BUILD_PROFILE%"=="debug" if /I not "%BUILD_PROFILE%"=="release" goto usage
if /I not "%BUILD_BACKEND%"=="cpu" if /I not "%BUILD_BACKEND%"=="cuda" goto usage
where cargo >nul 2>&1
if errorlevel 1 (echo ERRO: cargo nao foi encontrado no PATH. Execute rustinstall.bat primeiro.& exit /b 1)
set "BUILD_FLAGS="
if /I "%BUILD_PROFILE%"=="release" set "BUILD_FLAGS=--release"
if /I "%BUILD_BACKEND%"=="cuda" (
    call cuda\build_windows.bat %BUILD_PROFILE%
    if errorlevel 1 exit /b 1
    set "BUILD_FLAGS=%BUILD_FLAGS% --features cuda"
)
cargo build --target-dir target %BUILD_FLAGS%
if errorlevel 1 (echo ERRO: a compilacao %BUILD_PROFILE% falhou.& exit /b 1)
echo Build %BUILD_PROFILE% / %BUILD_BACKEND% concluido em target\%BUILD_PROFILE%.
exit /b 0
:usage
echo Uso: %~nx0 [debug^|release] [cpu^|cuda]
exit /b 2
