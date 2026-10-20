from django.db import migrations

# Nakala ya DEFAULT_SETTINGS wakati migration hii ilipoandikwa — migrations
# hazitakiwi kuimport models.py (inaweza kubadilika baadaye).
DEFAULTS = {
    'label_low': ('0.40', 'Confidence ya "Low" kwenye dataset'),
    'label_medium': ('0.65', 'Confidence ya "Medium" (kama R0001)'),
    'label_high': ('0.85', 'Confidence ya "High" (kama R0002)'),
    'range_strategy': ('mid', 'Thamani ya ranges (+0.15–+0.30): mid, min au max'),
    'confidence_cap': ('0.95', 'Kikomo cha juu cha confidence'),
    'diagnosis_threshold': ('0.75', 'Kiwango cha chini kutoa uchunguzi'),
    'min_lead_margin': ('0.15', 'Tofauti ya chini kati ya wa kwanza na wa pili'),
    'severity_low_max': ('10', 'Ukubwa (%) chini ya hapa = Low'),
    'severity_medium_max': ('30', 'Ukubwa (%) hadi hapa = Medium; juu = High'),
    'allow_product_names': ('0', 'SAFE001: 1 tu baada ya registry ya dawa kuidhinishwa'),
}


def add_defaults(apps, schema_editor):
    EngineSetting = apps.get_model('diagnosis', 'EngineSetting')
    for key, (value, description) in DEFAULTS.items():
        EngineSetting.objects.get_or_create(
            key=key, defaults={'value': value, 'description': description})


class Migration(migrations.Migration):
    dependencies = [('diagnosis', '0001_initial')]
    operations = [migrations.RunPython(add_defaults, migrations.RunPython.noop)]
