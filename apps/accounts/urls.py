from django.contrib.auth import views as auth_views
from django.urls import path

from .views import SignupView

app_name = "accounts"

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    # POST-only in Django; GET returns 405.
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
