from django.test import RequestFactory, SimpleTestCase

from config.ratelimit import client_ip


class ClientIpKeyTests(SimpleTestCase):
    rf = RequestFactory()

    def test_rightmost_xff_entry_used(self):
        req = self.rf.get("/", HTTP_X_FORWARDED_FOR="198.51.100.1, 203.0.113.9")
        self.assertEqual(client_ip(req), "203.0.113.9")

    def test_spoofed_leading_entry_ignored(self):
        a = self.rf.get("/", HTTP_X_FORWARDED_FOR="1.1.1.1, 203.0.113.9")
        b = self.rf.get("/", HTTP_X_FORWARDED_FOR="2.2.2.2,203.0.113.9")
        self.assertEqual(client_ip(a), client_ip(b))

    def test_remote_addr_fallback(self):
        req = self.rf.get("/", REMOTE_ADDR="192.0.2.4")
        self.assertEqual(client_ip(req), "192.0.2.4")
