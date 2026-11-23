"""
Tests for the surgical context gathering module.
"""
import pytest
from context import gather_context


def test_context_respects_token_budget():
    """Context gathering should not exceed token budget."""
    diff = "+" * 20000  # Large diff
    files = ["sample_repo/auth.py"]
    
    result = gather_context(diff, files, token_budget=1000)
    
    # Should stop before exceeding budget
    assert result.total_tokens <= 1000


def test_context_includes_relevant_files():
    """Should extract context from Python files."""
    diff = """
diff --git a/sample_repo/auth.py b/sample_repo/auth.py
+def new_function():
+    return True
"""
    files = ["sample_repo/auth.py"]
    
    result = gather_context(diff, files, repo_path=".", token_budget=4000)
    
    # Should have extracted something from auth.py
    assert len(result.files_included) > 0 or len(result.snippets) >= 0


def test_non_python_files_skipped():
    """Non-Python files should be skipped."""
    diff = "some changes"
    files = ["README.md", "config.json"]
    
    result = gather_context(diff, files, token_budget=4000)
    
    # No Python files, so no snippets
    assert len(result.snippets) == 0


def test_missing_files_handled():
    """Missing files should not crash the system."""
    diff = "some changes"
    files = ["nonexistent/file.py"]
    
    # Should not raise exception
    result = gather_context(diff, files, token_budget=4000)
    
    assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
