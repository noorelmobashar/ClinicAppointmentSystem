from django import forms
from accounts.models import CustomUser

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