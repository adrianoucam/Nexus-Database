@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if exist "Cargo.toml" (
    call build_once_windows.bat release
    if errorlevel 1 exit /b 1
) else (
    if not exist "target\release\nexusdb.exe" (
        echo ERRO: coloque o executavel release em target\release\nexusdb.exe.
        echo Este repositorio de distribuicao nao contem os fontes Rust do servidor.
        exit /b 1
    )
)

set "ISCC_EXE=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not exist "%ISCC_EXE%" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if not exist "%ISCC_EXE%" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_EXE%" (
    echo ERRO: Inno Setup 6 ou 7 nao foi encontrado.
    echo Instale pelo site oficial: https://jrsoftware.org/isinfo.php
    exit /b 1
)

if not exist "Docs\Manual_NexusDB_Comandos_e_Exemplos.docx" (
    echo ERRO: manual do NexusDB nao encontrado em Docs.
    exit /b 1
)

"%ISCC_EXE%" "installer\nexusdb.iss"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo ERRO: o Inno Setup terminou com codigo %EXIT_CODE%.
    exit /b %EXIT_CODE%
)

echo Instalador criado em installer\output.
exit /b 0
