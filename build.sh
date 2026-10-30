#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
# Data ya sample ya kanuni — inaingizwa TU kama database haina data bado,
# ili deploy isifute data ambayo mteja amepakia kupitia dashboard.
python manage.py import_mhd007 diagnosis/fixtures/mhd007 --if-empty
python manage.py import_advisory advisory/fixtures --if-empty
