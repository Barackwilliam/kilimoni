from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('bot', '0001_initial'),
    ]
    operations = [
        migrations.AddField(
            model_name='user',
            name='session_state',
            field=models.JSONField(default=dict, blank=True, help_text='Hifadhi hali ya mazungumzo - pending_location, pending_followup n.k.'),
        ),
        migrations.AddField(
            model_name='user',
            name='last_crop_id',
            field=models.IntegerField(null=True, blank=True, help_text='Zao la mwisho lililotajwa'),
        ),
        migrations.AddField(
            model_name='user',
            name='last_intent',
            field=models.CharField(max_length=100, blank=True, help_text='Intent ya mwisho iliyotambuliwa'),
        ),
    ]
