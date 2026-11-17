import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


def load_settings(**env):
    base = {k: v for k, v in os.environ.items() if k not in ("K_SERVICE", "REDIS_URL", "REDIS_CA_FILE")}
    return subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        env={**base, "DJANGO_SECRET_KEY": "test", **env},
        cwd=settings.BASE_DIR, capture_output=True, text=True,
    )


class RedisGuardTests(SimpleTestCase):
    def test_cloud_run_without_redis_url_raises(self):
        result = load_settings(K_SERVICE="entr-community")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn("REDIS_URL", result.stderr)

    def test_cloud_run_with_redis_url_loads(self):
        self.assertEqual(load_settings(K_SERVICE="entr-community", REDIS_URL="redis://redis:6379/0").returncode, 0)

    def test_local_without_redis_url_loads(self):
        self.assertEqual(load_settings().returncode, 0)
