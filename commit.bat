@echo off
REM ============================================
REM VMS - Script de Commits Atomicos
REM ============================================
setlocal enabledelayedexpansion

REM Cores (opcional, funciona no Windows 10+)
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "BLUE=[94m"
set "RESET=[0m"

echo %BLUE%========================================%RESET%
echo %BLUE%   VMS - Commit Atomico%RESET%
echo %BLUE%========================================%RESET%
echo.

REM Verificar se estamos em um repositorio git
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERRO] Nao esta em um repositorio Git!%RESET%
    exit /b 1
)

REM Mostrar status atual
echo %YELLOW%Status atual:%RESET%
git status --short
echo.

REM Verificar se ha mudancas
git diff-index --quiet HEAD --
if %errorlevel% equ 0 (
    echo %GREEN%Nenhuma mudanca para commitar.%RESET%
    exit /b 0
)

REM Menu de tipos de commit
echo %BLUE%Selecione o tipo de commit:%RESET%
echo.
echo  1. feat      - Nova funcionalidade
echo  2. fix       - Correcao de bug
echo  3. docs      - Documentacao
echo  4. style     - Formatacao (sem mudanca de logica)
echo  5. refactor  - Refatoracao de codigo
echo  6. test      - Adicionar/corrigir testes
echo  7. chore     - Manutencao (deps, config)
echo  8. perf      - Melhoria de performance
echo  9. ci        - CI/CD
echo 10. build     - Sistema de build
echo.

set /p tipo="Digite o numero (1-10): "

REM Mapear numero para tipo
if "%tipo%"=="1" set "commit_type=feat"
if "%tipo%"=="2" set "commit_type=fix"
if "%tipo%"=="3" set "commit_type=docs"
if "%tipo%"=="4" set "commit_type=style"
if "%tipo%"=="5" set "commit_type=refactor"
if "%tipo%"=="6" set "commit_type=test"
if "%tipo%"=="7" set "commit_type=chore"
if "%tipo%"=="8" set "commit_type=perf"
if "%tipo%"=="9" set "commit_type=ci"
if "%tipo%"=="10" set "commit_type=build"

if not defined commit_type (
    echo %RED%[ERRO] Opcao invalida!%RESET%
    exit /b 1
)

echo.
REM Escopo (opcional)
echo %BLUE%Escopo (opcional, ex: cameras, events, auth):%RESET%
set /p escopo="Escopo (Enter para pular): "

REM Mensagem curta
echo.
echo %BLUE%Mensagem curta (obrigatoria):%RESET%
set /p mensagem="Mensagem: "

if "%mensagem%"=="" (
    echo %RED%[ERRO] Mensagem obrigatoria!%RESET%
    exit /b 1
)

REM Construir mensagem de commit
if "%escopo%"=="" (
    set "commit_msg=%commit_type%: %mensagem%"
) else (
    set "commit_msg=%commit_type%(%escopo%): %mensagem%"
)

echo.
echo %YELLOW%Mensagem do commit:%RESET%
echo %GREEN%%commit_msg%%RESET%
echo.

REM Confirmar
set /p confirma="Confirmar commit? (s/N): "
if /i not "%confirma%"=="s" (
    echo %YELLOW%Commit cancelado.%RESET%
    exit /b 0
)

REM Adicionar todos os arquivos modificados
echo.
echo %BLUE%Adicionando arquivos...%RESET%
git add -A

REM Fazer commit
echo %BLUE%Fazendo commit...%RESET%
git commit -m "%commit_msg%"

if errorlevel 1 (
    echo %RED%[ERRO] Falha ao fazer commit!%RESET%
    exit /b 1
)

echo.
echo %GREEN%========================================%RESET%
echo %GREEN%   Commit realizado com sucesso!%RESET%
echo %GREEN%========================================%RESET%
echo.

REM Perguntar se quer fazer push
set /p push="Fazer push para origin? (s/N): "
if /i "%push%"=="s" (
    echo %BLUE%Fazendo push...%RESET%
    git push
    if errorlevel 1 (
        echo %RED%[ERRO] Falha ao fazer push!%RESET%
        exit /b 1
    )
    echo %GREEN%Push realizado com sucesso!%RESET%
)

echo.
echo %BLUE%Ultimo commit:%RESET%
git log -1 --oneline
echo.

endlocal
