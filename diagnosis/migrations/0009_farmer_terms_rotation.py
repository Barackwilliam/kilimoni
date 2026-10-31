from django.db import migrations

# Maneno mapya ya kamusi (mzunguko wa mazao, MHD-006 R4)
TERMS = [('same botanical family', 'mazao ya familia moja'), ('pest/disease carryover', 'wadudu na magonjwa kubaki shambani'), ('nutrient mining', 'kumaliza virutubisho vya udongo'), ('risk ya', 'hatari ya'), ('monocropping', 'kulima zao moja kila msimu'), ('diversification', 'kuchanganya mazao'), ('rotation', 'mzunguko wa mazao'), ('solanaceae crops', 'mazao ya jamii ya nyanya na viazi'), ('legumes', 'mikunde'), ('legume', 'mikunde'), ('cereal', 'nafaka'), ('cover crop', 'mazao ya kufunika udongo'), ('crop cover', 'mazao ya kufunika udongo'), ('heavy feeder', 'hutumia virutubisho vingi'), ('break crop', 'zao la kuvunja mzunguko')]


def seed(apps, schema_editor):
    FarmerTerm = apps.get_model('diagnosis', 'FarmerTerm')
    for term, plain in TERMS:
        FarmerTerm.objects.get_or_create(term=term, defaults={'plain': plain})


class Migration(migrations.Migration):
    dependencies = [('diagnosis', '0008_farmer_terms_soil')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
