from django.db import migrations, models


def backfill_wavepagequestion_sort_order(apps, schema_editor):
    WavePageQuestion = apps.get_model("pages", "WavePageQuestion")

    current_page_id = None
    current_order = 0

    qs = (
        WavePageQuestion.objects
        .all()
        .order_by("wave_page_id", "question_id", "id")
    )

    updates = []

    for link in qs.iterator():
        if link.wave_page_id != current_page_id:
            current_page_id = link.wave_page_id
            current_order = 1
        else:
            current_order += 1

        link.sort_order = current_order
        updates.append(link)

    if updates:
        WavePageQuestion.objects.bulk_update(updates, ["sort_order"])


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0015_wavepaqgeqml"),
    ]

    operations = [
        migrations.AddField(
            model_name="wavepagequestion",
            name="sort_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(
            backfill_wavepagequestion_sort_order,
            migrations.RunPython.noop,
        ),
        migrations.AlterUniqueTogether(
            name="wavepagequestion",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="wavepagequestion",
            constraint=models.UniqueConstraint(
                fields=("wave_page", "question"),
                name="uq_wavepagequestion_page_question",
            ),
        ),
        migrations.AddIndex(
            model_name="wavepagequestion",
            index=models.Index(
                fields=["wave_page", "sort_order"],
                name="idx_wpq_page_sort",
            ),
        ),
    ]