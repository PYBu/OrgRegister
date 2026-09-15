import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend import mail
from backend.parser import MailAccount, parse_line
from backend.proxy import parse_proxy


class ParserTests(unittest.TestCase):
    def test_parse_six_part_line(self):
        account = parse_line("a@outlook.com----pw----uuid----refresh----tmp@example.com----tmp-pw")
        self.assertIsInstance(account, MailAccount)
        self.assertEqual(account.ms_uuid, "uuid")

    def test_reject_wrong_part_count(self):
        self.assertIsNone(parse_line("a----b----c----d----e"))


class ProxyTests(unittest.TestCase):
    def test_authenticated_proxy_preserves_colons_and_escapes_credentials(self):
        proxy = parse_proxy("1.2.3.4:8080:user name:p:a:ss")
        self.assertEqual(proxy.server, "http://1.2.3.4:8080")
        self.assertEqual(proxy.username, "user name")
        self.assertEqual(proxy.password, "p:a:ss")
        self.assertEqual(proxy.to_requests()["https"], "http://user%20name:p%3Aa%3Ass@1.2.3.4:8080")

    def test_empty_proxy(self):
        self.assertEqual(parse_proxy("").server, "")


class MailTests(unittest.TestCase):
    def test_graph_datetime_parser_and_since_filter(self):
        self.assertEqual(
            mail._parse_graph_datetime("2026-09-15T00:00:00Z"),
            datetime(2026, 9, 15, tzinfo=timezone.utc),
        )
        since = datetime(2026, 9, 15, 0, 10, tzinfo=timezone.utc)
        messages = [
            {
                "receivedDateTime": "2026-09-14T23:00:00Z",
                "subject": "Your code is 111111",
                "from": {},
                "body": {"content": ""},
                "bodyPreview": "Your code is 111111",
            }
        ]
        self.assertIsNone(mail._graph_code(messages, None, since))

    def test_since_grace_accepts_small_clock_skew(self):
        since = datetime.now(timezone.utc)
        self.assertTrue(mail._after_grace(since - timedelta(seconds=30), since))
        self.assertFalse(mail._after_grace(since - timedelta(seconds=mail.config.MAIL_CODE_SINCE_GRACE + 1), since))

    def test_graph_filter_failure_retries_without_filter(self):
        account = MailAccount("a@outlook.com", "pw", "uuid", "refresh", "tmp@example.com", "tmp-pw")
        responses = [
            type("Response", (), {"status_code": 400, "json": lambda self: {}})(),
            type("Response", (), {"status_code": 200, "json": lambda self: {"value": [{"receivedDateTime": "2026-09-15T00:00:00Z", "subject": "Your code is 123456", "from": {}, "body": {"content": ""}, "bodyPreview": "Your code is 123456"}]}})(),
        ]
        with patch.object(mail, "exchange_access_token", return_value="access"), patch.object(mail.requests, "get", side_effect=responses) as get:
            code = mail._graph_fetch(account, None, None, datetime(2026, 9, 15, tzinfo=timezone.utc))
        self.assertEqual(code, "123456")
        self.assertEqual(get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
