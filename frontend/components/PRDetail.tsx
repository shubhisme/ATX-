"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getJob, type Finding, type Job } from "@/lib/api";
import StatusBadge from "./StatusBadge";
import { ArrowLeft, Clock, DollarSign, Cpu, ShieldCheck, AlertCircle, Zap, Code2 } from "lucide-react";

const POLL_MS = 2000;

const SEVERITY_CONFIG: Record<
  string,
  { badge: string; text: string; border: string }
> = {
  critical: {
    badge: "bg-rose-500/15 text-rose-300 border-rose-500/40",
    text: "CRITICAL",
    border: "border-l-rose-500",
  },
  warning: {
    badge: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    text: "WARNING",
    border: "border-l-amber-500",
  },
  info: {
    badge: "bg-sky-500/15 text-sky-300 border-sky-500/40",
    text: "INFO",
    border: "border-l-sky-500",
  },
  suggestion: {
    badge: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
    text: "SUGGESTION",
    border: "border-l-emerald-500",
  },
};

interface DiffLine {
  kind: "header" | "hunk" | "add" | "del" | "ctx";
  text: string;
  file: string | null;
  newLine: number | null;
}

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
  header: "text-slate-400 bg-slate-900/90 font-semibold border-b border-slate-800",
  hunk: "bg-indigo-950/40 text-indigo-300 font-semibold border-y border-indigo-900/40",
  add: "bg-emerald-950/30 text-emerald-300 border-l-2 border-emerald-500",
  del: "bg-rose-950/30 text-rose-300 border-l-2 border-rose-500",
  ctx: "text-slate-400",
};

function FindingCard({ f }: { f: Finding }) {
  const sevKey = (f.severity || "info").toLowerCase();
  const conf = SEVERITY_CONFIG[sevKey] || SEVERITY_CONFIG.info;

  return (
    <div
      className={`my-2 ml-8 rounded-xl border border-slate-800 bg-slate-900/95 p-4 font-sans text-xs shadow-lg shadow-black/40 border-l-4 ${conf.border}`}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full border px-2.5 py-0.5 text-xs font-bold tracking-wide uppercase ${conf.badge}`}
          >
            {conf.text}
          </span>
          <span className="text-slate-400 uppercase font-mono font-semibold">
            {f.category}
          </span>
        </div>
        <span className="font-mono text-slate-500">
          {f.file_path}:{f.line_number}
        </span>
      </div>

      <div className="text-slate-200 text-sm font-medium leading-relaxed">
        {f.message}
      </div>

      {f.suggestion && (
        <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950 p-2.5 font-mono text-xs text-slate-300">
          <div className="text-emerald-400 font-semibold mb-1 flex items-center gap-1.5">
            <Code2 className="h-3.5 w-3.5" />
            Suggested Improvement:
          </div>
          <div className="whitespace-pre-wrap">{f.suggestion}</div>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
        <span>{label}</span>
        {icon}
      </div>
      <div className="mt-2 text-xl font-bold font-mono text-white">{value}</div>
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

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex items-center gap-3 text-slate-400 font-mono text-sm">
          <div className="h-5 w-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          Loading PR details...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
        {error}
      </div>
    );
  }

  if (!job) {
    return (
      <div className="text-center py-16 text-slate-400">
        Job <span className="font-mono text-white">{id}</span> not found.
      </div>
    );
  }

  const lines = parseDiff(job.diff_content);

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
    <div className="space-y-8 max-w-6xl mx-auto py-4">
      {/* Back button */}
      <div>
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Live Queue
        </Link>
      </div>

      {/* Hero Header */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold text-white tracking-tight">
                Pull Request #{job.pr_number}
              </h2>
              <StatusBadge status={job.status} />
              {job.cache_hit && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 border border-amber-500/30 px-2.5 py-0.5 text-xs font-semibold text-amber-300">
                  <Zap className="h-3 w-3" />
                  CACHE HIT
                </span>
              )}
            </div>
            <div className="mt-2 flex items-center gap-3 text-xs text-slate-400 font-mono">
              <span>Commit: <span className="text-slate-200">{job.commit_sha}</span></span>
              <span>•</span>
              <span>Job ID: <span className="text-slate-200">{job.job_id}</span></span>
            </div>
          </div>
        </div>

        {/* Telemetry Strip */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat
            label="Wall-clock Latency"
            value={job.latency_ms != null ? `${job.latency_ms} ms` : "—"}
            icon={<Clock className="h-4 w-4 text-cyan-400" />}
          />
          <Stat
            label="Token Consumption"
            value={
              job.tokens_in != null
                ? `${job.tokens_in.toLocaleString()} / ${job.tokens_out?.toLocaleString()}`
                : "0 tokens"
            }
            icon={<Cpu className="h-4 w-4 text-indigo-400" />}
          />
          <Stat
            label="Incurred Spend"
            value={job.cost_usd != null ? `$${job.cost_usd.toFixed(4)}` : "$0.0000"}
            icon={<DollarSign className="h-4 w-4 text-emerald-400" />}
          />
          <Stat
            label="AI Findings"
            value={String(job.findings.length)}
            icon={<AlertCircle className="h-4 w-4 text-amber-400" />}
          />
        </div>
      </div>

      {/* Deterministic Pre-LLM Gates */}
      {job.gate_results.length > 0 && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-md">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Pre-LLM Deterministic Gates (&lt;100ms)
            </h3>
          </div>
          <div className="space-y-2">
            {job.gate_results.map((g, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-xl border border-slate-800/80 bg-slate-950/60 p-3 text-xs"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-md px-2 py-0.5 font-bold uppercase ${
                      g.status === "PASS"
                        ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                        : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                    }`}
                  >
                    {g.status}
                  </span>
                  <span className="font-semibold text-slate-200">
                    {g.check_type}
                  </span>
                  {g.details && (
                    <span className="text-slate-400 font-mono">
                      {g.details}
                    </span>
                  )}
                </div>
                <span className="font-mono text-slate-400">
                  {g.duration_ms} ms
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Diff & Inline Review Findings */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-md">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Unified Git Diff & Inline AI Findings
          </h3>
          <span className="text-xs text-slate-500 font-mono">
            {lines.length} lines parsed
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 font-mono text-xs">
          {lines.map((l, i) => (
            <div key={i}>
              <div
                className={`flex whitespace-pre px-3 py-0.5 hover:bg-slate-900/50 transition-colors ${
                  LINE_STYLES[l.kind]
                }`}
              >
                <span className="w-10 shrink-0 select-none text-right text-slate-600 pr-3">
                  {l.newLine ?? ""}
                </span>
                <span className="pl-2">{l.text}</span>
              </div>
              {l.newLine != null &&
                l.file &&
                job.findings
                  .filter(
                    (f) =>
                      f.file_path === l.file && f.line_number === l.newLine
                  )
                  .map((f) => <FindingCard key={f.finding_id} f={f} />)}
            </div>
          ))}
        </div>
      </div>

      {/* Other / Unanchored Findings */}
      {unanchored.length > 0 && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-md">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-4">
            Repository-Level Findings ({unanchored.length})
          </h3>
          <div className="space-y-3">
            {unanchored.map((f) => (
              <FindingCard key={f.finding_id} f={f} />
            ))}
          </div>
        </div>
      )}

      {job.findings.length === 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 text-center text-xs text-slate-500">
          {job.status === "STATIC_FAILED"
            ? "PR rejected by pre-LLM static gates. Zero LLM tokens consumed."
            : "No findings reported for this diff."}
        </div>
      )}
    </div>
  );
}
