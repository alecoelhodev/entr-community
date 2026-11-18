from django.contrib.auth import views as auth_views
from django.urls import path

from config.ratelimit import client_ip, ratelimit

from .views import SignupView


def login_email(request):
    return request.POST.get("username", "").strip().lower()


login_view = auth_views.LoginView.as_view(template_name="accounts/login.html", redirect_authenticated_user=True)
login_view = ratelimit("login-ip", client_ip, "10/15m")(ratelimit("login-email", login_email, "20/h")(login_view))

app_name = "accounts"

urlpatterns = [
    path("signup/", ratelimit("signup-ip", client_ip, "5/h")(SignupView.as_view()), name="signup"),
    path("login/", login_view, name="login"),
    # POST-only in Django; GET returns 405.
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
