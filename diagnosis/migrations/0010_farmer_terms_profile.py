from django.db import migrations

# Maneno mapya ya kamusi (Hatua 6)
TERMS = [('high n demand', 'huhitaji naitrojeni (N) nyingi'), ('good before', 'hufaa kabla ya'), ('cereal/grass', 'nafaka/nyasi')]


def seed(apps, schema_editor):
    FarmerTerm = apps.get_model('diagnosis', 'FarmerTerm')
    for term, plain in TERMS:
        FarmerTerm.objects.get_or_create(term=term, defaults={'plain': plain})


class Migration(migrations.Migration):
    dependencies = [('diagnosis', '0009_farmer_terms_rotation')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
