"""轻量单元测试：验证改写、进程过滤、录制、重放逻辑。"""

import json
import tempfile
import unittest
from pathlib import Path

from interceptor.main import rewrite_payload
from interceptor.process_filter import ProcessFilter
from interceptor.recorder import Recorder
from interceptor.replay import parse_http_request


class RewritePayloadTests(unittest.TestCase):
	def test_rewrites_option_a(self):
		body = b"csrfmiddlewaretoken=abc&order=1&selected_option=A"
		self.assertEqual(
			rewrite_payload(body),
			b"csrfmiddlewaretoken=abc&order=1&selected_option=E",
		)

	def test_rewrites_option_d_in_middle(self):
		body = b"selected_option=D&trailing=1"
		self.assertEqual(rewrite_payload(body), b"selected_option=E&trailing=1")

	def test_returns_none_when_no_field(self):
		self.assertIsNone(rewrite_payload(b"foo=bar"))

	def test_returns_none_when_already_invalid(self):
		self.assertIsNone(rewrite_payload(b"selected_option=Z"))

	def test_does_not_match_substring(self):
		# selected_option=Apple 不应该被改写
		self.assertIsNone(rewrite_payload(b"selected_option=Apple"))

	def test_keeps_payload_length(self):
		body = b"selected_option=B"
		rewritten = rewrite_payload(body)
		self.assertIsNotNone(rewritten)
		self.assertEqual(len(rewritten), len(body))


class ProcessFilterTests(unittest.TestCase):
	def _provider(self, entries):
		def _wrapped():
			return iter(entries)
		return _wrapped

	def test_inactive_filter_allows_everything(self):
		pf = ProcessFilter()
		self.assertTrue(pf.matches("127.0.0.1", 12345))

	def test_matches_by_pid(self):
		provider = self._provider([("127.0.0.1", 5555, 4242, "chrome.exe")])
		pf = ProcessFilter(allowed_pids=[4242], snapshot_provider=provider)
		self.assertTrue(pf.matches("127.0.0.1", 5555))
		self.assertFalse(pf.matches("127.0.0.1", 5556))

	def test_matches_by_name_case_insensitive(self):
		provider = self._provider([("127.0.0.1", 6000, 100, "Chrome.EXE")])
		pf = ProcessFilter(allowed_names=["chrome.exe"], snapshot_provider=provider)
		self.assertTrue(pf.matches("127.0.0.1", 6000))

	def test_falls_back_to_wildcard_listen_addr(self):
		provider = self._provider([("0.0.0.0", 7000, 99, "service.exe")])
		pf = ProcessFilter(allowed_pids=[99], snapshot_provider=provider)
		self.assertTrue(pf.matches("127.0.0.1", 7000))

	def test_normalizes_ipv6_mapped(self):
		provider = self._provider([("127.0.0.1", 8000, 11, "py.exe")])
		pf = ProcessFilter(allowed_pids=[11], snapshot_provider=provider)
		self.assertTrue(pf.matches("::ffff:127.0.0.1", 8000))


class RecorderTests(unittest.TestCase):
	def test_writes_record_with_payloads(self):
		with tempfile.TemporaryDirectory() as tmp:
			recorder = Recorder(tmp)
			path = recorder.record(
				src_addr="127.0.0.1",
				src_port=12345,
				dst_addr="127.0.0.1",
				dst_port=8000,
				original=b"selected_option=A",
				rewritten=b"selected_option=E",
				pid=4242,
				process_name="chrome.exe",
			)
			self.assertTrue(Path(path).exists())
			data = json.loads(Path(path).read_text(encoding="utf-8"))
			self.assertEqual(data["src"], {"addr": "127.0.0.1", "port": 12345})
			self.assertEqual(data["dst"], {"addr": "127.0.0.1", "port": 8000})
			self.assertEqual(data["pid"], 4242)
			self.assertEqual(data["process"], "chrome.exe")
			self.assertEqual(data["original_text"], "selected_option=A")
			self.assertEqual(data["rewritten_text"], "selected_option=E")
			# base64 应能还原回原始字节
			import base64
			self.assertEqual(base64.b64decode(data["original_b64"]), b"selected_option=A")
			self.assertEqual(base64.b64decode(data["rewritten_b64"]), b"selected_option=E")


class ReplayParserTests(unittest.TestCase):
	def test_parses_post_request(self):
		raw = (
			b"POST /attempt/1/answer/ HTTP/1.1\r\n"
			b"Host: 127.0.0.1:8000\r\n"
			b"Content-Type: application/x-www-form-urlencoded\r\n"
			b"Content-Length: 17\r\n"
			b"\r\n"
			b"selected_option=A"
		)
		method, path, headers, body = parse_http_request(raw)
		self.assertEqual(method, "POST")
		self.assertEqual(path, "/attempt/1/answer/")
		self.assertEqual(headers["Host"], "127.0.0.1:8000")
		self.assertEqual(headers["Content-Type"], "application/x-www-form-urlencoded")
		self.assertEqual(body, b"selected_option=A")

	def test_raises_on_missing_separator(self):
		with self.assertRaises(ValueError):
			parse_http_request(b"GET / HTTP/1.1\r\nHost: x\r\n")


if __name__ == "__main__":
	unittest.main()

