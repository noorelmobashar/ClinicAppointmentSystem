from django.db import models


class WalkInPatient(models.Model):
    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
