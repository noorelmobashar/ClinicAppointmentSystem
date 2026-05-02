from unittest.mock import patch, MagicMock
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from appointments.models import Appointment, AppointmentSlot
from payments.models import PaymentTransaction
import stripe

User = get_user_model()


class PaymentsViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(
            username="patient1",
            email="patient1@test.com",
            password="password123",
            role=User.Role.PATIENT
        )
        self.doctor = User.objects.create_user(
            username="doctor1",
            email="doctor1@test.com",
            password="password123",
            role=User.Role.DOCTOR
        )
        self.slot = AppointmentSlot.objects.create(
            doctor=self.doctor,
            date=timezone.now().date(),
            start_time="10:00:00",
            end_time="10:30:00",
            is_booked=False
        )
        self.checkout_url = reverse("stripe-checkout", args=[self.slot.id])

    def test_payment_success_view_unauthenticated(self):
        response = self.client.get(reverse("payment-success"))
        self.assertRedirects(response, f"/accounts/login/?next={reverse('payment-success')}", fetch_redirect_response=False)

    @patch("payments.views.render")
    def test_payment_success_view_authenticated(self, mock_render):
        from django.http import HttpResponse
        mock_render.return_value = HttpResponse("ok")
        self.client.force_login(self.patient)
        response = self.client.get(reverse("payment-success"))
        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()
        self.assertEqual(mock_render.call_args[0][1], "payments/success.html")

    @patch("payments.views.render")
    def test_payment_cancel_view_authenticated(self, mock_render):
        from django.http import HttpResponse
        mock_render.return_value = HttpResponse("ok")
        self.client.force_login(self.patient)
        response = self.client.get(reverse("payment-cancel"))
        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()
        self.assertEqual(mock_render.call_args[0][1], "payments/cancel.html")

    @patch("stripe.checkout.Session.create")
    def test_create_checkout_session_success(self, mock_create):
        self.client.force_login(self.patient)
        
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test-url"
        mock_create.return_value = mock_session

        response = self.client.get(self.checkout_url)
        
        self.assertRedirects(response, "https://checkout.stripe.com/test-url", fetch_redirect_response=False)
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        self.assertEqual(call_kwargs["metadata"]["slot_id"], str(self.slot.id))
        self.assertEqual(call_kwargs["metadata"]["patient_id"], str(self.patient.id))

    def test_create_checkout_session_slot_already_booked(self):
        self.client.force_login(self.patient)
        self.slot.is_booked = True
        self.slot.save()

        response = self.client.get(self.checkout_url)
        self.assertRedirects(response, reverse("patient-booking"), fetch_redirect_response=False)
        
        # Check messages
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "The session is already booked by another user.")


class StripeWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(
            username="patient2",
            password="password123",
            role=User.Role.PATIENT
        )
        self.doctor = User.objects.create_user(
            username="doctor2",
            password="password123",
            role=User.Role.DOCTOR
        )
        self.slot = AppointmentSlot.objects.create(
            doctor=self.doctor,
            date=timezone.now().date(),
            start_time="11:00:00",
            end_time="11:30:00",
            is_booked=False
        )
        self.webhook_url = reverse("stripe-webhook")

    @patch("stripe.Webhook.construct_event")
    def test_webhook_invalid_signature(self, mock_construct):
        mock_construct.side_effect = stripe.error.SignatureVerificationError("Invalid", "sig")
        
        response = self.client.post(self.webhook_url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_checkout_session_completed(self, mock_construct):
        mock_event = MagicMock()
        mock_event.type = "checkout.session.completed"
        
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.metadata = {
            "slot_id": str(self.slot.id),
            "patient_id": str(self.patient.id)
        }
        mock_session.amount_total = 20000
        mock_event.data.object = mock_session
        
        mock_construct.return_value = mock_event

        response = self.client.post(self.webhook_url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 200)

        self.slot.refresh_from_db()
        self.assertTrue(self.slot.is_booked)

        appointment = Appointment.objects.get(slot=self.slot)
        self.assertEqual(appointment.patient, self.patient)
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)

        txn = PaymentTransaction.objects.get(appointment=appointment)
        self.assertEqual(txn.stripe_checkout_id, "cs_test_123")
        self.assertEqual(txn.amount, Decimal("200.00"))
        self.assertEqual(txn.status, PaymentTransaction.Status.PAID)

    @patch("stripe.Refund.create")
    @patch("stripe.Webhook.construct_event")
    def test_webhook_slot_already_booked_refunds(self, mock_construct, mock_refund):
        self.slot.is_booked = True
        self.slot.save()

        mock_event = MagicMock()
        mock_event.type = "checkout.session.completed"
        
        mock_session = MagicMock()
        mock_session.id = "cs_test_456"
        mock_session.payment_intent = "pi_test_123"
        mock_session.metadata = {
            "slot_id": str(self.slot.id),
            "patient_id": str(self.patient.id)
        }
        mock_event.data.object = mock_session
        
        mock_construct.return_value = mock_event

        response = self.client.post(self.webhook_url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 200)

        # Ensure refund was called
        mock_refund.assert_called_once_with(payment_intent="pi_test_123")
        
        # Ensure appointment wasn't created
        self.assertEqual(Appointment.objects.filter(slot=self.slot).count(), 0)
