from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0008_doctorschedule_schedule_date_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[],
            reverse_sql=[],
        )
    ]
