#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
# Data ya rules engine (MHD-007). Upsert kwa ID — salama kurudia kila deploy.
python manage.py import_mhd007 diagnosis/fixtures/mhd007
