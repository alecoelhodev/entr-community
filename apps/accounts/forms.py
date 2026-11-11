from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, BaseUserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _

from .models import User, normalize_email


class EmailNormalizingMixin:
    def clean_email(self):
        return normalize_email(self.cleaned_data["email"])


class SignupForm(EmailNormalizingMixin, BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("first_name", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }
        help_texts = {"email": _("Used to log in. Never shown publicly.")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["first_name"].widget.attrs["autofocus"] = True
        self.fields["email"].widget.attrs.pop("autofocus", None)
        self.fields["password1"].help_text = ""
        self.fields["password2"].label = _("Confirm password")
        self.fields["password2"].help_text = ""


class UserAdminCreationForm(EmailNormalizingMixin, AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


class UserAdminChangeForm(EmailNormalizingMixin, UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
