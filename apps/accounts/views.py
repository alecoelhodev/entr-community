from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import SignupForm


class SignupView(FormView):
    template_name = "accounts/signup.html"
    form_class = SignupForm
    success_url = reverse_lazy("directory:map")

    def form_valid(self, form):
        login(self.request, form.save())
        return super().form_valid(form)
