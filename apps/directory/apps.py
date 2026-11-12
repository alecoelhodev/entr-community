from django.apps import AppConfig


class DirectoryConfig(AppConfig):
    name = "apps.directory"

    def ready(self):
        from . import ratings  # noqa: F401  (registers the review delete signal)
