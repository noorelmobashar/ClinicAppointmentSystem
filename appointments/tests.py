from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import DoctorProfile
from appointments.models import AppointmentSlot


class BookingViewsTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.patient = self.user_model.objects.create_user(
            username="patient1",
            email="patient@example.com",
            password="pass12345",
            role="PATIENT",
        )
        self.doctor_1 = self.user_model.objects.create_user(
            username="sara",
            first_name="Sara",
            last_name="Ibrahim",
            email="sara@example.com",
            password="pass12345",
            role="DOCTOR",
        )
        self.doctor_2 = self.user_model.objects.create_user(
            username="mohamed",
            first_name="Mohamed",
            last_name="Adel",
            email="mohamed@example.com",
            password="pass12345",
            role="DOCTOR",
        )
        DoctorProfile.objects.create(
            user=self.doctor_1,
            specialty="Cardiology",
            bio="Heart specialist",
            consultation_fee=300,
        )
        DoctorProfile.objects.create(
            user=self.doctor_2,
            specialty="Dermatology",
            bio="Skin specialist",
            consultation_fee=250,
        )
        self.client.force_login(self.patient)

    def test_booking_page_filters_by_query_and_specialty(self):
        response = self.client.get(reverse("patient-booking"), {
            "q": "Sara",
            "specialty": "Cardiology",
        })

        doctors = list(response.context["doctors"])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(doctors, [self.doctor_1])
        self.assertContains(response, "Heart specialist")
        self.assertNotContains(response, "Skin specialist")

    def test_doctor_profile_page_loads_database_content(self):
        AppointmentSlot.objects.create(
            doctor=self.doctor_1,
            date=date(2030, 1, 5),
            start_time=time(10, 0),
            end_time=time(10, 30),
            is_booked=False,
        )

        response = self.client.get(reverse("doctor-public-profile", args=[self.doctor_1.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cardiology")
        self.assertContains(response, "Heart specialist")
        self.assertContains(response, "$300.00")
