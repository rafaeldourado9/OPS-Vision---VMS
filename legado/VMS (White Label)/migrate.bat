@echo off
cd infra
docker-compose exec django python manage.py migrate
