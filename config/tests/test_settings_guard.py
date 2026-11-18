import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


def load_settings(code="import config.settings", **env):
    base = {k: v for k, v in os.environ.items() if k not in ("K_SERVICE", "REDIS_URL")}
    return subprocess.run(
        [sys.executable, "-c", code],
        env={**base, "DJANGO_SECRET_KEY": "test", **env},
        cwd=settings.BASE_DIR, capture_output=True, text=True,
    )


class RedisGuardTests(SimpleTestCase):
    def test_cloud_run_without_redis_url_raises(self):
        result = load_settings(K_SERVICE="entr-community")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn("REDIS_URL", result.stderr)

    def test_cloud_run_plain_redis_url_raises(self):
        result = load_settings(K_SERVICE="entr-community", REDIS_URL="redis://redis.example.com:6379/0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rediss://", result.stderr)

    def test_cloud_run_with_tls_redis_url_loads(self):
        result = load_settings(K_SERVICE="entr-community", REDIS_URL="rediss://:pw@redis.example.com:6380/0")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_redis_cache_is_namespaced(self):
        # The production instance may be shared with other apps.
        code = "import config.settings as s; assert s.CACHES['default']['KEY_PREFIX'] == 'entr'"
        result = load_settings(code, REDIS_URL="redis://redis:6379/0")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_without_redis_url_loads(self):
        self.assertEqual(load_settings().returncode, 0)
