from django.db import migrations

# Settings mpya za rules engine (nakala — migrations haziimport models.py)
DEFAULTS = {
    'initial_source': ('007D', 'Chanzo cha score ya mwanzo kikiwa na vingi: 007D au 007A'),
    'symptom_match_ratio': ('0.5', 'Sehemu ya maneno ya dalili yanayotakiwa kulingana'),
    'key_question_no_adjustment': ('-0.125', 'Ishara kuu ikikataliwa (katikati ya -0.05..-0.20 ya 007C)'),
    'rec_min_severity': ('high', 'Severity ya chini kwa Recommendation Rule (low/medium/high)'),
    'max_questions': ('4', 'Idadi ya juu ya maswali ya kufuatilia kwa uchunguzi mmoja'),
}


def add_defaults(apps, schema_editor):
    EngineSetting = apps.get_model('diagnosis', 'EngineSetting')
    for key, (value, description) in DEFAULTS.items():
        EngineSetting.objects.get_or_create(
            key=key, defaults={'value': value, 'description': description})


class Migration(migrations.Migration):
    dependencies = [('diagnosis', '0003_mhd007b_007d')]
    operations = [migrations.RunPython(add_defaults, migrations.RunPython.noop)]
