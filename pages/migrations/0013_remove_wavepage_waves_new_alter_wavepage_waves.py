from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0012_copy_waves_to_wavepagewave'),
        ('waves', '0016_wavequestion_uq_wavequestion_wave_question'),
    ]

    operations = [
        # 1) Altes Auto-M2M entfernen -> droppt pages_wavepage_waves
        migrations.RemoveField(
            model_name='wavepage',
            name='waves',
        ),

        # 2) Neues through-M2M (waves_new) auf den alten Namen umbenennen
        migrations.RenameField(
            model_name='wavepage',
            old_name='waves_new',
            new_name='waves',
        ),

        # 3) Feldattribute finalisieren (bleibt M2M mit through)
        migrations.AlterField(
            model_name='wavepage',
            name='waves',
            field=models.ManyToManyField(
                blank=True,
                related_name='pages',
                through='pages.WavePageWave',
                to='waves.wave',
                help_text='Befragtengruppen, die diese Seite sehen.',
            ),
        ),
    ]