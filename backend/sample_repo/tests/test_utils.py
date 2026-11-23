"""Unit tests for the utils module."""

import os
import sys
import unittest

# Ensure sample_repo is importable
_cur_dir = os.path.dirname(os.path.abspath(__file__))
_sample_dir = os.path.dirname(_cur_dir)
_backend_dir = os.path.dirname(_sample_dir)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _sample_dir not in sys.path:
    sys.path.insert(0, _sample_dir)

try:
    from sample_repo.utils import (
        format_response,
        generate_id,
        sanitize_input,
        validate_email,
    )
except ImportError:
    from utils import (  # type: ignore
        format_response,
        generate_id,
        sanitize_input,
        validate_email,
    )


class TestSanitizeInput(unittest.TestCase):
    """Tests for :func:`sanitize_input`."""

    def test_removes_angle_brackets(self) -> None:
        self.assertEqual(sanitize_input("<script>alert(1)</script>"), "scriptalert(1)/script")

    def test_collapses_whitespace(self) -> None:
        self.assertEqual(sanitize_input("  hello   world  "), "hello world")

    def test_empty_string(self) -> None:
        self.assertEqual(sanitize_input(""), "")


class TestValidateEmail(unittest.TestCase):
    """Tests for :func:`validate_email`."""

    def test_valid_email(self) -> None:
        self.assertTrue(validate_email("user@example.com"))

    def test_invalid_email_no_at(self) -> None:
        self.assertFalse(validate_email("userexample.com"))

    def test_invalid_email_no_domain(self) -> None:
        self.assertFalse(validate_email("user@"))


class TestFormatResponse(unittest.TestCase):
    """Tests for :func:`format_response`."""

    def test_default_status(self) -> None:
        resp = format_response({"key": "value"})
        self.assertEqual(resp["status"], 200)
        self.assertIn("timestamp", resp)

    def test_custom_status(self) -> None:
        resp = format_response(None, status=404)
        self.assertEqual(resp["status"], 404)


class TestGenerateId(unittest.TestCase):
    """Tests for :func:`generate_id`."""

    def test_returns_hex_string(self) -> None:
        uid = generate_id()
        self.assertEqual(len(uid), 32)
        int(uid, 16)  # should not raise

    def test_unique_ids(self) -> None:
        ids = {generate_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)


if __name__ == "__main__":
    unittest.main()
