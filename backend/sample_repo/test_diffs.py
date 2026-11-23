"""
Pre-packaged realistic PR diffs and payloads for the Batch Simulator and testing.

Provides 5 distinct test scenarios:
1. CLEAN_FEATURE — valid new helper in utils.py (passes gates, LLM review)
2. SECRET_LEAK — hardcoded AWS access key (fails gate in <10ms, $0 spend)
3. SYNTAX_ERROR — missing colon / broken indentation (fails syntax check, $0 spend)
4. CACHE_HIT_TARGET — predictable SHA to verify commit-SHA dedup caching
5. SURGICAL_CONTEXT — changes in app.py that exercise import resolution (auth, db, utils)
"""

SAMPLE_PR_DIFFS = {
    "clean_feature": {
        "title": "Add retry decorator and exponential backoff utility",
        "branch": "feature/retry-helper",
        "commit_sha": "a1b2c3d4e5f67890123456789abcdef01234567",
        "pr_number": 101,
        "changed_files": [
            {
                "path": "utils.py",
                "content": """import time
import functools

def retry_with_backoff(retries=3, backoff_factor=1.5):
    \"\"\"Decorator that retries a function with exponential backoff.\"\"\"
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = 1.0
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:
                        raise e
                    time.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator
""",
            }
        ],
        "diff_content": """--- a/utils.py
+++ b/utils.py
@@ -35,3 +35,21 @@ def generate_id() -> str:
     \"\"\"Generate a random hexadecimal identifier.\"\"\"
     return uuid.uuid4().hex
+
+def retry_with_backoff(retries=3, backoff_factor=1.5):
+    \"\"\"Decorator that retries a function with exponential backoff.\"\"\"
+    def decorator(func):
+        @functools.wraps(func)
+        def wrapper(*args, **kwargs):
+            delay = 1.0
+            for attempt in range(retries):
+                try:
+                    return func(*args, **kwargs)
+                except Exception as e:
+                    if attempt == retries - 1:
+                        raise e
+                    time.sleep(delay)
+                    delay *= backoff_factor
+        return wrapper
+    return decorator
""",
    },
    "secret_leak": {
        "title": "Add AWS S3 bucket backup configuration",
        "branch": "bugfix/s3-credentials",
        "commit_sha": "bad0000000000000000000000000000000000001",
        "pr_number": 102,
        "changed_files": [
            {
                "path": "config.py",
                "content": """AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'
AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
S3_BUCKET = 'company-production-backups'
""",
            }
        ],
        "diff_content": """--- a/config.py
+++ b/config.py
@@ -10,2 +10,5 @@ MAX_RETRIES = 3
+AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'
+AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
+S3_BUCKET = 'company-production-backups'
""",
    },
    "syntax_error": {
        "title": "Refactor auth token verification",
        "branch": "refactor/auth-syntax-bug",
        "commit_sha": "bad0000000000000000000000000000000000002",
        "pr_number": 103,
        "changed_files": [
            {
                "path": "auth.py",
                "content": """def verify_token(token: str) -> bool
    # Missing colon and invalid syntax
    if not token
        return False
""",
            }
        ],
        "diff_content": """--- a/auth.py
+++ b/auth.py
@@ -20,4 +20,4 @@ def verify_token(token: str) -> bool:
-def verify_token(token: str) -> bool:
-    return token.startswith("tok_")
+def verify_token(token: str) -> bool
+    if not token
+        return False
""",
    },
    "surgical_context": {
        "title": "Add new user profile update route",
        "branch": "feature/user-profile-update",
        "commit_sha": "c0ffee11223344556677889900aabbccddeeff00",
        "pr_number": 104,
        "changed_files": [
            {
                "path": "app.py",
                "content": """# Modified app.py with new route calling auth and database
from auth import verify_token
from database import fetch_user, save_record
from utils import sanitize_input, format_response

def update_user_profile(token: str, user_id: str, profile_data: dict):
    if not verify_token(token):
        return format_response({"error": "Unauthorized"}, 401)
    
    clean_bio = sanitize_input(profile_data.get("bio", ""))
    save_record("users", {"id": user_id, "bio": clean_bio})
    return format_response({"status": "updated"}, 200)
""",
            }
        ],
        "diff_content": """--- a/app.py
+++ b/app.py
@@ -50,3 +50,11 @@ def get_user_profile(token: str, user_id: str):
     return format_response(user, 200)
+
+def update_user_profile(token: str, user_id: str, profile_data: dict):
+    if not verify_token(token):
+        return format_response({"error": "Unauthorized"}, 401)
+    
+    clean_bio = sanitize_input(profile_data.get("bio", ""))
+    save_record("users", {"id": user_id, "bio": clean_bio})
+    return format_response({"status": "updated"}, 200)
""",
    },
}
