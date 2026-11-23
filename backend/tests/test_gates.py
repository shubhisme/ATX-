"""
Tests for the deterministic gate module.
"""
import pytest
from gates import run_gate


def test_clean_code_passes_gate():
    """Clean code should pass all gate checks."""
    diff = """
diff --git a/test.py b/test.py
+def hello():
+    return "world"
"""
    result = run_gate(diff, ["test.py"])
    
    assert result.passed is True
    assert len(result.errors) == 0


def test_aws_key_detected():
    """AWS keys should be detected and fail gate."""
    diff = """
diff --git a/config.py b/config.py
+AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
"""
    result = run_gate(diff, ["config.py"])
    
    assert result.passed is False
    assert any("AWS Access Key" in err for err in result.errors)


def test_github_token_detected():
    """GitHub tokens should be detected."""
    diff = """
diff --git a/config.py b/config.py
+TOKEN = "ghp_1234567890abcdefghijklmnopqrstuv"
"""
    result = run_gate(diff, ["config.py"])
    
    assert result.passed is False
    assert any("GitHub Token" in err for err in result.errors)


def test_private_key_detected():
    """Private keys should be detected."""
    diff = """
diff --git a/keys.pem b/keys.pem
+-----BEGIN PRIVATE KEY-----
+MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7
+-----END PRIVATE KEY-----
"""
    result = run_gate(diff, ["keys.pem"])
    
    assert result.passed is False
    assert any("Private Key" in err for err in result.errors)


def test_python_syntax_error_detected():
    """Python syntax errors should be caught."""
    diff = """
diff --git a/broken.py b/broken.py
+def broken():
+    if True
+        print("missing colon")
"""
    result = run_gate(diff, ["broken.py"])
    
    assert result.passed is False
    assert any("syntax error" in err.lower() for err in result.errors)


def test_valid_python_syntax():
    """Valid Python code should pass."""
    diff = """
diff --git a/valid.py b/valid.py
+def valid():
+    if True:
+        print("correct syntax")
+    return None
"""
    result = run_gate(diff, ["valid.py"])
    
    assert result.passed is True


def test_multiple_issues():
    """Multiple issues should all be reported."""
    diff = """
diff --git a/bad.py b/bad.py
+API_KEY = "AKIAIOSFODNN7EXAMPLE"
+def broken():
+    if True
+        print("broken")
"""
    result = run_gate(diff, ["bad.py"])
    
    assert result.passed is False
    assert len(result.errors) >= 2  # At least secret + syntax error


def test_non_python_files_ignored():
    """Non-Python files shouldn't trigger syntax checks."""
    diff = """
diff --git a/README.md b/README.md
+# Title
+This is not Python code and should not be parsed
"""
    result = run_gate(diff, ["README.md"])
    
    assert result.passed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
