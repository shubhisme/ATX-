"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getJob, type Finding, type Job } from "@/lib/api";
import StatusBadge from "./StatusBadge";

const POLL_MS = 2000;

const SEVERITY_STYLES: Record<string, string> = {
    Critical: "bg-red-100 text-red-700 border-red-300",
    Warning: "bg-yellow-100 text-yellow-700 border-yellow-300",
    Info: "bg-blue-100 text-blue-700 border-blue-300",
};

interface DiffLine {
    kind: "header" | "hunk" | "add" | "del" | "ctx";
    text: string;
    file: string | null;
    newLine: number | null;
}

// Turns a unified diff into lines tagged with their new-file line number,
// so findings (which carry file_path + line_number) can be anchored.
function parseDiff(diff: string): DiffLine[] {
    const out: DiffLine[] = [];
    let file: string | null = null;
    let newLine = 0;

    for (const raw of diff.split("\n")) {
        if (raw.startsWith("--- ")) {
            out.push({ kind: "header", text: raw, file, newLine: null });
        } else if (raw.startsWith("+++ ")) {
            file = raw.replace(/^\+\+\+ (b\/)?/, "").trim();
            out.push({ kind: "header", text: raw, file, newLine: null });
        } else if (raw.startsWith("@@")) {
            const m = raw.match(/\+(\d+)/);
            newLine = m ? parseInt(m[1], 10) : 0;
            out.push({ kind: "hunk", text: raw, file, newLine: null });
        } else if (raw.startsWith("+")) {
            out.push({ kind: "add", text: raw, file, newLine });
            newLine++;
        } else if (raw.startsWith("-")) {
            out.push({ kind: "del", text: raw, file, newLine: null });
        } else {
            out.push({ kind: "ctx", text: raw, file, newLine });
            newLine++;
        }
    }
    return out;
}

const LINE_STYLES: Record<DiffLine["kind"], string> = {
    header: "text-gray-500",
    hunk: "bg-blue-50 text-blue-700",
    add: "bg-green-50 text-green-800",
    del: "bg-red-50 text-red-800",
    ctx: "text-gray-700",
};

function FindingCard({ f }: { f: Finding }) {
    return (
        <div className="my-1 ml-10 rounded border border-gray-300 bg-white p-3 font-sans text-sm">
        <div className="mb-1 flex items-center gap-2">
        <span
        className={`rounded border px-2 py-0.5 text-xs font-medium ${
            SEVERITY_STYLES[f.severity] ?? SEVERITY_STYLES.Info
        }`}
        >
        {f.severity}
        </span>
        <span className="text-xs text-gray-500">{f.category}</span>
        <span className="text-xs text-gray-400">
        {f.file_path}:{f.line_number}
        </span>
        </div>
        <div>{f.message}</div>
        {f.suggestion && (
            <div className="mt-1 text-gray-600">
            <span className="font-medium">Suggestion:</span> {f.suggestion}
            </div>
        )}
        </div>
    );
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded border p-3">
        <div className="text-xs text-gray-500">{label}</div>
        <div className="text-lg font-semibold">{value}</div>
        </div>
    );
}

export default function PRDetail({ id }: { id: string }) {
    const [job, setJob] = useState<Job | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        const load = async () => {
            try {
                const data = await getJob(id);
                if (active) {
                    setJob(data);
                    setError(null);
                    setLoading(false);
                }
            } catch (e) {
                if (active) {
                    setError(e instanceof Error ? e.message : "Failed to load job");
                    setLoading(false);
                }
            }
        };
        load();
        const timer = setInterval(load, POLL_MS);
        return () => {
            active = false;
            clearInterval(timer);
        };
    }, [id]);

    if (loading) return <div className="text-gray-500">Loading…</div>;
    if (error) {
        return (
            <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
            </div>
        );
    }
    if (!job) return <div className="text-gray-500">Job {id} not found.</div>;

    const lines = parseDiff(job.diff_content);

    // Findings that match a diff line get shown inline; the rest go in a list below.
    const anchored = new Set<string>();
    for (const l of lines) {
        if (l.newLine != null && l.file) {
            for (const f of job.findings) {
                if (f.file_path === l.file && f.line_number === l.newLine) {
                    anchored.add(f.finding_id);
                }
            }
        }
    }
    const unanchored = job.findings.filter((f) => !anchored.has(f.finding_id));

    return (
        <div className="space-y-6">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
        ← Back to queue
        </Link>

        <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">
        PR #{job.pr_number} · {job.job_id}
        </h2>
        <StatusBadge status={job.status} />
        {job.cache_hit && (
            <span className="rounded bg-purple-100 px-2 py-0.5 text-xs text-purple-700">
            CACHE HIT
            </span>
        )}
        <span className="font-mono text-sm text-gray-500">
        {job.commit_sha.slice(0, 7)}
        </span>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
        label="Latency"
        value={job.latency_ms != null ? `${job.latency_ms} ms` : "—"}
        />
        <Stat
        label="Tokens in / out"
        value={
            job.tokens_in != null ? `${job.tokens_in} / ${job.tokens_out}` : "—"
        }
        />
        <Stat
        label="Cost"
        value={job.cost_usd != null ? `$${job.cost_usd.toFixed(4)}` : "—"}
        />
        <Stat label="Findings" value={String(job.findings.length)} />
        </div>

        {job.gate_results.length > 0 && (
            <div>
            <h3 className="mb-2 font-medium">Static gate</h3>
            <div className="space-y-1 text-sm">
            {job.gate_results.map((g, i) => (
                <div key={i} className="flex items-center gap-2">
                <span
                className={`rounded border px-2 py-0.5 text-xs font-medium ${
                    g.status === "PASS"
                    ? "border-green-300 bg-green-100 text-green-700"
                    : "border-red-300 bg-red-100 text-red-700"
                }`}
                >
                {g.status}
                </span>
                <span>{g.check_type}</span>
                <span className="text-gray-400">{g.duration_ms} ms</span>
                {g.details && <span className="text-gray-600">{g.details}</span>}
                </div>
            ))}
            </div>
            </div>
        )}

        <div>
        <h3 className="mb-2 font-medium">Diff</h3>
        <div className="overflow-x-auto rounded border bg-gray-50 font-mono text-sm">
        {lines.map((l, i) => (
            <div key={i}>
            <div className={`flex whitespace-pre px-2 ${LINE_STYLES[l.kind]}`}>
            <span className="w-8 shrink-0 select-none text-right text-gray-400">
            {l.newLine ?? ""}
            </span>
            <span className="pl-2">{l.text}</span>
            </div>
            {l.newLine != null &&
                l.file &&
                job.findings
                .filter(
                    (f) => f.file_path === l.file && f.line_number === l.newLine
                )
                .map((f) => <FindingCard key={f.finding_id} f={f} />)}
                </div>
        ))}
        </div>
        </div>

        {unanchored.length > 0 && (
            <div>
            <h3 className="mb-2 font-medium">Other findings</h3>
            {unanchored.map((f) => (
                <FindingCard key={f.finding_id} f={f} />
            ))}
            </div>
        )}

        {job.findings.length === 0 && (
            <div className="text-sm text-gray-500">
            {job.status === "STATIC_FAILED"
                ? "Rejected by the static gate. The LLM was not called."
                : "No findings yet."}
                </div>
        )}
        </div>
    );
}
