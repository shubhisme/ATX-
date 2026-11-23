import type { Finding } from "./api";

export interface Sample {
    id: string;
    label: string;
    diff: string;
    findings: Finding[];
}

export const CLEAN_SAMPLES: Sample[] = [
    {
        id: "docstring",
        label: "Clean change",
        diff: [
            "--- a/utils.py",
            "+++ b/utils.py",
            "@@ -1,2 +1,3 @@",
            " def helper(x):",
            '+    """Return x doubled."""',
            "     return x * 2",
        ].join("\n"),
        findings: [],
    },
{
    id: "sql-injection",
    label: "SQL injection",
    diff: [
        "--- a/database.py",
        "+++ b/database.py",
        "@@ -4,2 +4,2 @@",
        " def get_user(uid):",
        '-    return db.query("SELECT * FROM users WHERE id = ?", uid)',
        '+    return db.query(f"SELECT * FROM users WHERE id = {uid}")',
    ].join("\n"),
    findings: [
        {
            finding_id: "f-sql-1",
            file_path: "database.py",
            line_number: 5,
            severity: "Critical",
            category: "security",
            message:
            "User input is interpolated straight into the SQL string, which allows SQL injection.",
            suggestion: "Use a parameterized query: db.query(sql, (uid,)).",
        },
    ],
},
{
    id: "missing-import",
    label: "Missing import",
    diff: [
        "--- a/auth.py",
        "+++ b/auth.py",
        "@@ -10,4 +10,4 @@",
        " def login(user, password):",
        '-    if password == "admin123":',
        "+    if check_hash(password, user.hash):",
        "         return True",
    ].join("\n"),
    findings: [
        {
            finding_id: "f-imp-1",
            file_path: "auth.py",
            line_number: 11,
            severity: "Warning",
            category: "correctness",
            message: "check_hash is not imported in this file.",
            suggestion: "Add: from utils import check_hash",
        },
    ],
},
];

// AWS's documented example key, so GitHub push protection doesn't flag it.
export const SECRET_SAMPLE: Sample = {
    id: "secret-leak",
    label: "Hardcoded AWS key",
    diff: [
        "--- a/config.py",
        "+++ b/config.py",
        "@@ -1,2 +1,3 @@",
        '+AWS_KEY = "AKIAIOSFODNN7EXAMPLE"',
        " DEBUG = True",
    ].join("\n"),
    findings: [],
};

export function findSample(diff: string): Sample | undefined {
    return [...CLEAN_SAMPLES, SECRET_SAMPLE].find((s) => s.diff === diff);
}
