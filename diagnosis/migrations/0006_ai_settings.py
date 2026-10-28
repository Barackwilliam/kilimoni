from django.db import migrations

# Settings za tabaka la AI la lugha (nakala — migrations haziimport models.py)
DEFAULTS = {
    'ai_language': ('1', 'AI ielewe lugha ya mkulima (dalili, majibu, ukubwa): 1 = ndiyo, 0 = maneno tu'),
    'ai_summary': ('1', 'AI iandike aya fupi ya kibinadamu juu ya jibu (inakaguliwa): 1 = ndiyo, 0 = hapana'),
}


def add_defaults(apps, schema_editor):
    EngineSetting = apps.get_model('diagnosis', 'EngineSetting')
    for key, (value, description) in DEFAULTS.items():
        EngineSetting.objects.get_or_create(key=key, defaults={'value': value, 'description': description})


class Migration(migrations.Migration):
    dependencies = [('diagnosis', '0005_farmer_terms')]
    operations = [migrations.RunPython(add_defaults, migrations.RunPython.noop)]
