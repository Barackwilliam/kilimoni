from django.db import migrations

# Maneno mapya ya kamusi (ushauri wa udongo, MHD-004)
TERMS = [('phosphorus management', 'matumizi sahihi ya mbolea yenye fosforasi'), ('organic matter', 'mboji/samadi'), ('lime/fertilizer', 'chokaa au mbolea'), ('liming', 'kuweka chokaa'), ('kutegemea landscape', 'kutegemea mwinuko wa ardhi'), ('subsoil nzito', 'udongo wa chini mzito'), ('subsoil', 'udongo wa chini'), ('topsoil', 'udongo wa juu'), ('drainage', 'mtiririko wa maji'), ('phosphorus', 'fosforasi'), ('clay loam', 'tifutifu ya mfinyanzi'), ('mulching', 'kufunika udongo kwa matandazo'), ('suitability', 'ufaafu')]


def seed(apps, schema_editor):
    FarmerTerm = apps.get_model('diagnosis', 'FarmerTerm')
    for term, plain in TERMS:
        FarmerTerm.objects.get_or_create(term=term, defaults={'plain': plain})


class Migration(migrations.Migration):
    dependencies = [('diagnosis', '0007_farmer_terms_seeds')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
