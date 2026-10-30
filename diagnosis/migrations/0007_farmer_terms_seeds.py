from django.db import migrations

# Maneno mapya ya kamusi (ushauri wa mbegu, MHD-003A)
TERMS = [
    ('TOSCI grain yield', 'majaribio ya TOSCI'),
    ('variety hii', 'mbegu hii'),
    ('variety', 'aina ya mbegu'),
]


def seed(apps, schema_editor):
    FarmerTerm = apps.get_model('diagnosis', 'FarmerTerm')
    for term, plain in TERMS:
        FarmerTerm.objects.get_or_create(term=term, defaults={'plain': plain})


class Migration(migrations.Migration):
    dependencies = [('diagnosis', '0006_ai_settings')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
