from django import forms
from accounts.models import CustomUser, DoctorProfile, PatientProfile

SPECIALTY_CHOICES = [
    ("Cardiology", "Cardiology"),
    ("Dermatology", "Dermatology"),
    ("Neurology", "Neurology"),
    ("Pediatrics", "Pediatrics"),
    ("General Medicine", "General Medicine"),
]

BLOOD_TYPE_CHOICES = [
    ("A+", "A+"),
    ("A-", "A-"),
    ("B+", "B+"),
    ("B-", "B-"),
    ("AB+", "AB+"),
    ("AB-", "AB-"),
    ("O+", "O+"),
    ("O-", "O-"),
]

class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField()


class RegisterForm(forms.ModelForm):
    password = forms.CharField()
    confirm_password = forms.CharField()
    role = forms.ChoiceField(choices=CustomUser.Role.choices)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'role']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match")

        return cleaned_data


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField()


class ResetPasswordForm(forms.Form):
    new_password = forms.CharField()
    confirm_password = forms.CharField()

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match")

        return cleaned_data


class ChangePasswordForm(ResetPasswordForm):
    old_password = forms.CharField()


class BaseProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["username", "first_name", "last_name", "phone_number"]


class DoctorProfileForm(forms.ModelForm):
    class Meta:
        model = DoctorProfile
        fields = ["specialty", "bio", "consultation_fee"]
        widgets = {
            "consultation_fee": forms.NumberInput(attrs={"step": "0.01"}),
        }


class PatientProfileForm(forms.ModelForm):
    class Meta:
        model = PatientProfile
        fields = ["date_of_birth", "blood_type"]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }


class DoctorOnboardingForm(forms.ModelForm):
    specialty = forms.ChoiceField(
        choices=SPECIALTY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Share a short summary of your clinical focus.",
            }
        ),
    )
    consultation_fee = forms.DecimalField(
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "placeholder": "Enter consultation fee",
            }
        ),
    )

    class Meta:
        model = DoctorProfile
        fields = ["specialty", "bio", "consultation_fee"]


class PatientOnboardingForm(forms.ModelForm):
    blood_type = forms.ChoiceField(
        choices=BLOOD_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    class Meta:
        model = PatientProfile
        fields = ["blood_type", "date_of_birth"]