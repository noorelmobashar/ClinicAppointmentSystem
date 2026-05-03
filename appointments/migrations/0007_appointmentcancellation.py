import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0006_appointment_active_patient_doctor_day"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AppointmentCancellation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("previous_status", models.CharField(choices=[("REQUESTED", "Requested"), ("AWAITING_PAYMENT", "Awaiting payment"), ("CONFIRMED", "Confirmed"), ("CANCELLED", "Cancelled"), ("CHECKED_IN", "Checked in"), ("COMPLETED", "Completed")], max_length=20)),
                ("reason", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("appointment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cancellation_history", to="appointments.appointment")),
                ("cancelled_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="appointment_cancellations", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
