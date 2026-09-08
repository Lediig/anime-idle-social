@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo == Carta do Dia: atualizar agenda e enviar pro GitHub ==
echo.
git pull --rebase -q origin main
python bot\carta.py calendario >nul
if errorlevel 1 (echo ERRO ao gerar a agenda. & pause & exit /b 1)
git add data\pular.txt CALENDARIO.md CALENDARIO.html
git diff --cached --quiet && (echo Nada mudou. A agenda local foi refeita.) || (
  git commit -q -m "agenda: pular.txt e calendario" && git push -q origin HEAD:main && echo Enviado. O GitHub refaz o calendario online em 1 minuto.
)
echo.
start "" "CALENDARIO.html"
pause
