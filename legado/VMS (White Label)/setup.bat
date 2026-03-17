@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   VMS White Label - Setup Automatico
echo ========================================
echo.

cd /d "%~dp0infra"

echo [1/2] Criando superuser (admin@gtvision.com / Admin123!)...
docker compose exec -T django python manage.py createsuperuser --email admin@gtvision.com --noinput 2>nul
if %errorlevel% equ 0 (
    echo       Superuser criado.
    docker compose exec -T django python -c "from apps.auth_app.models import User; u=User.objects.get(email='admin@gtvision.com'); u.set_password('Admin123!'); u.save()"
) else (
    echo       Superuser ja existe, OK.
)

echo.
echo [2/2] Criando reseller, licencas e tenant...
docker compose exec -T django python manage.py setup_tenant --domain localhost --subdomain localhost --license 500

echo.
echo Pronto! Acesse http://localhost
echo Login: admin@gtvision.com / Admin123!
echo.
pause
