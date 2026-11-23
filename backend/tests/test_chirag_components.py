"""
Comprehensive Test Suite for Chirag's Components (Person B - Intelligence Layer):
1. Deterministic Gates (secret scanning, syntax check, gate runner)
2. Context Engine (import resolver, symbol reader, diff context builder)
3. Agent Layer (token tracker, prompt formatting)
4. Sample Repository (integrity and import chain)
"""

import asyncio
import os
import sys
import unittest

# Add backend to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from gates.secret_scanner import scan_secrets
from gates.syntax_checker import check_syntax, check_syntax_from_diff
from gates.gate_runner import run_static_gates
from context.dependency_resolver import resolve_dependencies, get_imported_symbols
from context.symbol_reader import read_symbol_context, extract_all_symbols, build_context_for_diff
from agent.token_tracker import TokenTracker
from agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from models import JobStatus, GateResultResponse, ReviewResultResponse


class TestDeterministicGates(unittest.TestCase):
    def test_secret_scanner_detects_secrets(self):
        diff = (
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "@@ -1,2 +1,4 @@\n"
            "+AWS_KEY = 'AKIA1234567890ABCDEF'\n"
            "+JWT = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0'\n"
            "+GH_PAT = 'ghp_123456789012345678901234567890123456'\n"
        )
        findings = scan_secrets(diff)
        self.assertGreaterEqual(len(findings), 3)
        pattern_names = [f.pattern_name for f in findings]
        self.assertIn("AWS Access Key", pattern_names)
        self.assertIn("JWT Token", pattern_names)
        self.assertIn("GitHub Token (ghp)", pattern_names)
        # Verify secrets are redacted
        for f in findings:
            self.assertTrue("*" in f.matched_text)

    def test_secret_scanner_clean_diff(self):
        diff = (
            "--- a/utils.py\n"
            "+++ b/utils.py\n"
            "@@ -10,3 +10,4 @@\n"
            "+def clean_function(x):\n"
            "+    return x * 2\n"
        )
        findings = scan_secrets(diff)
        self.assertEqual(len(findings), 0)

    def test_syntax_checker(self):
        valid_code = "def foo():\n    return 42\n"
        invalid_code = "def foo(\n    broken syntax"
        res_valid = check_syntax("foo.py", valid_code)
        self.assertTrue(res_valid.valid)
        self.assertIsNone(res_valid.error_message)

        res_invalid = check_syntax("broken.py", invalid_code)
        self.assertFalse(res_invalid.valid)
        self.assertIsNotNone(res_invalid.error_message)

    def test_gate_runner_orchestrator(self):
        async def run():
            diff_clean = (
                "--- a/app.py\n"
                "+++ b/app.py\n"
                "@@ -1,2 +1,3 @@\n"
                "+# Clean comment\n"
            )
            files_clean = [{"path": "app.py", "content": "print('hello')\n"}]
            res = await run_static_gates(diff_clean, files_clean)
            self.assertTrue(res.passed)
            self.assertEqual(len(res.failed_checks), 0)
            self.assertLess(res.duration_ms, 100.0)  # PRD requirement: <100ms

            diff_bad = (
                "--- a/app.py\n"
                "+++ b/app.py\n"
                "@@ -1,2 +1,3 @@\n"
                "+API_KEY = 'sk-1234567890abcdef12345678'\n"
            )
            files_bad = [{"path": "app.py", "content": "def bad(\n"}]
            res_bad = await run_static_gates(diff_bad, files_bad)
            self.assertFalse(res_bad.passed)
            self.assertIn("secret_scan", res_bad.failed_checks)
            self.assertIn("syntax_check", res_bad.failed_checks)

        asyncio.run(run())


class TestContextEngine(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.path.join(BACKEND_DIR, "sample_repo")

    def test_import_resolution(self):
        app_file = os.path.join(self.repo_root, "app.py")
        imports = get_imported_symbols(app_file)
        self.assertGreater(len(imports), 0)

        # resolve_dependencies from app.py should discover auth.py, database.py, utils.py
        deps = resolve_dependencies(["app.py"], self.repo_root)
        dep_basenames = [os.path.basename(d) for d in deps]
        self.assertIn("auth.py", dep_basenames)
        self.assertIn("database.py", dep_basenames)
        self.assertIn("utils.py", dep_basenames)
        self.assertNotIn("app.py", dep_basenames)  # changed files are excluded

    def test_symbol_extraction(self):
        auth_file = os.path.join(self.repo_root, "auth.py")
        sym = read_symbol_context(auth_file, "hash_password")
        self.assertIsNotNone(sym)
        self.assertEqual(sym.symbol_name, "hash_password")
        self.assertEqual(sym.symbol_type, "function")
        self.assertIn("def hash_password", sym.source_code)

        all_syms = extract_all_symbols(auth_file)
        names = [s.symbol_name for s in all_syms]
        self.assertIn("hash_password", names)
        self.assertIn("verify_token", names)
        self.assertIn("create_session", names)

    def test_build_context_for_diff(self):
        context_str = build_context_for_diff(["app.py"], self.repo_root, token_budget=4000)
        self.assertIn("DIRECT DEPENDENCY CONTEXT", context_str)
        self.assertIn("auth.py", context_str)
        self.assertIn("database.py", context_str)
        self.assertIn("utils.py", context_str)
        # Ensure it contains extracted functions
        self.assertIn("hash_password", context_str)


class TestAgentLayer(unittest.TestCase):
    def test_token_tracker(self):
        tracker = TokenTracker(model_name="compound-beta")
        text = "Hello world, this is a test for token counting."
        tokens = tracker.count_tokens(text)
        self.assertGreater(tokens, 0)

        usage = tracker.track_request("Short prompt", "Short response")
        self.assertGreater(usage.total_tokens, 0)
        self.assertEqual(usage.estimated_cost_usd, 0.0)

    def test_prompt_formatting(self):
        formatted = USER_PROMPT_TEMPLATE.format(
            diff="--- a/test.py\n+++ b/test.py\n+x = 1\n",
            context="No extra context.",
            changed_files="- test.py",
        )
        self.assertIn("test.py", formatted)
        self.assertIn("+x = 1", formatted)


if __name__ == "__main__":
    unittest.main()
