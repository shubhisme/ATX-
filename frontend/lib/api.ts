import mock from "./mock-jobs.json";
import { findSample } from "./samples";

export type JobStatus =
  | "QUEUED"
  | "STATIC_FAILED"
  | "AI_REVIEWING"
  | "COMPLETED"
  | "SUPERSEDED";

export interface Finding {
  finding_id: string;
  file_path: string;
  line_number: number;
  severity: string;
  category: string;
  message: string;
  suggestion: string;
}

export interface GateResult {
  check_type: string;
  status: string;
  details: string;
  duration_ms: number;
}

export interface Job {
  job_id: string;
  pr_number: string;
  repo_url: string;
  commit_sha: string;
  status: JobStatus;
  cache_hit: boolean;
  created_at: number;
  started_at: number | null;
  completed_at: number | null;
  latency_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  diff_content: string;
  gate_results: GateResult[];
  findings: Finding[];
}

export interface SubmitPayload {
  repo_url: string;
  pr_number: string;
  commit_sha: string;
  diff_content: string;
  title?: string;
  files?: string[];
}

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const seed = mock.jobs as unknown as Job[];

// ---------------------------------------------------------------------------
// Mock mode: simulates submitted PRs moving through a 3-worker queue.
// State lives in browser memory and resets on page reload.
// ---------------------------------------------------------------------------

const WORKERS = 3;
const INPUT_USD_PER_TOKEN = 0.59 / 1_000_000;
const OUTPUT_USD_PER_TOKEN = 0.79 / 1_000_000;

interface SimJob {
  final: Job;
  kind: "ai" | "instant";
  startAt: number;
  endAt: number;
}

const sim: SimJob[] = [];
const workerFree: number[] = Array(WORKERS).fill(0);
const seenShas = new Set<string>(
  seed.filter((j) => j.status === "COMPLETED").map((j) => j.commit_sha)
);
let simCounter = 0;

const rand = (min: number, max: number) =>
  min + Math.floor(Math.random() * (max - min + 1));

function viewOf(s: SimJob, now: number): Job {
  if (s.kind === "instant") return s.final;
  if (now < s.startAt) {
    return {
      ...s.final,
      status: "QUEUED",
      started_at: null,
      completed_at: null,
      latency_ms: null,
      tokens_in: null,
      tokens_out: null,
      cost_usd: null,
      findings: [],
    };
  }
  if (now < s.endAt) {
    return {
      ...s.final,
      status: "AI_REVIEWING",
      started_at: s.startAt / 1000,
      completed_at: null,
      latency_ms: null,
      tokens_in: null,
      tokens_out: null,
      cost_usd: null,
      findings: [],
    };
  }
  return s.final;
}

function submitMock(p: SubmitPayload) {
  const now = Date.now();
  const sample = findSample(p.diff_content);
  simCounter += 1;
  const id = `job-sim-${Date.now().toString(36)}-${simCounter}`;

  const findings: Finding[] = (sample?.findings ?? []).map((f, i) => ({
    finding_id: `find-sim-${simCounter}-${i}`,
    file_path: f.file_path,
    line_number: f.line_number,
    severity: f.severity,
    category: f.category,
    message: f.message,
    suggestion: f.suggestion,
  }));

  const base: Job = {
    job_id: id,
    pr_number: p.pr_number,
    repo_url: p.repo_url,
    commit_sha: p.commit_sha,
    status: "QUEUED",
    cache_hit: false,
    created_at: now / 1000,
    started_at: null,
    completed_at: null,
    latency_ms: null,
    tokens_in: null,
    tokens_out: null,
    cost_usd: null,
    diff_content: p.diff_content,
    gate_results: [],
    findings: [],
  };

  // 1. Cache hit?
  if (seenShas.has(p.commit_sha)) {
    sim.push({
      kind: "instant",
      startAt: now,
      endAt: now + 50,
      final: {
        ...base,
        status: "COMPLETED",
        cache_hit: true,
        started_at: now / 1000,
        completed_at: (now + 50) / 1000,
        latency_ms: 50,
        tokens_in: 0,
        tokens_out: 0,
        cost_usd: 0,
        gate_results: [
          { check_type: "cache", status: "HIT", details: "commit SHA matches cached review", duration_ms: 2 },
        ],
        findings,
      },
    });
    return;
  }

  // 2. Secret leak rejection
  if (sample?.id === "secret-leak") {
    sim.push({
      kind: "instant",
      startAt: now,
      endAt: now + 12,
      final: {
        ...base,
        status: "STATIC_FAILED",
        cache_hit: false,
        started_at: now / 1000,
        completed_at: (now + 12) / 1000,
        latency_ms: 12,
        tokens_in: 0,
        tokens_out: 0,
        cost_usd: 0,
        gate_results: [
          {
            check_type: "secrets",
            status: "FAIL",
            details: "Hardcoded secret pattern detected in added lines",
            duration_ms: rand(1, 3),
          },
        ],
      },
    });
    return;
  }

  // 3. Queue for the first free worker
  const duration = rand(1200, 2800);
  const w = workerFree.indexOf(Math.min(...workerFree));
  const startAt = Math.max(now + 200, workerFree[w]);
  const endAt = startAt + duration;
  workerFree[w] = endAt;
  seenShas.add(p.commit_sha);

  const tokensIn = rand(1200, 2400);
  const tokensOut = rand(150, 400);

  sim.push({
    kind: "ai",
    startAt,
    endAt,
    final: {
      ...base,
      status: "COMPLETED",
      started_at: startAt / 1000,
      completed_at: endAt / 1000,
      latency_ms: duration,
      tokens_in: tokensIn,
      tokens_out: tokensOut,
      cost_usd: Number(
        (tokensIn * INPUT_USD_PER_TOKEN + tokensOut * OUTPUT_USD_PER_TOKEN).toFixed(6)
      ),
      gate_results: [
        { check_type: "secrets", status: "PASS", details: "", duration_ms: rand(1, 3) },
        { check_type: "syntax", status: "PASS", details: "", duration_ms: rand(1, 4) },
      ],
      findings,
    },
  });
}

// ---------------------------------------------------------------------------
// Normalizer for Backend API / Mock Compatibility
// ---------------------------------------------------------------------------

function normalizeJob(raw: any): Job {
  const findings: Finding[] = (raw.findings || raw.review?.findings || []).map((f: any, idx: number) => ({
    finding_id: String(f.finding_id || f.id || `f-${idx}`),
    file_path: f.file_path || f.file || "unknown",
    line_number: Number(f.line_number || f.line || 1),
    severity: f.severity || "info",
    category: f.category || "style",
    message: f.message || "",
    suggestion: f.suggestion || "",
  }));

  const gate_results: GateResult[] = Array.isArray(raw.gate_results)
    ? raw.gate_results
    : raw.static_result
    ? [
        {
          check_type: "deterministic_gates",
          status: raw.static_result.passed ? "PASS" : "FAIL",
          details: Array.isArray(raw.static_result.errors)
            ? raw.static_result.errors.join("; ")
            : "All static checks passed",
          duration_ms: raw.static_result.duration_ms || 1,
        },
      ]
    : [];

  return {
    job_id: String(raw.job_id ?? raw.id ?? ""),
    pr_number: String(raw.pr_number ?? ""),
    repo_url: raw.repo_url || "https://github.com/shubhisme/ATX-",
    commit_sha: raw.commit_sha || "",
    status: (raw.status as JobStatus) || "QUEUED",
    cache_hit: Boolean(raw.cache_hit),
    created_at: typeof raw.created_at === "number"
      ? raw.created_at
      : (raw.queued_at ? new Date(raw.queued_at).getTime() / 1000 : Date.now() / 1000),
    started_at: typeof raw.started_at === "number"
      ? raw.started_at
      : (raw.started_at ? new Date(raw.started_at).getTime() / 1000 : null),
    completed_at: typeof raw.completed_at === "number"
      ? raw.completed_at
      : (raw.completed_at ? new Date(raw.completed_at).getTime() / 1000 : null),
    latency_ms: raw.latency_ms ?? null,
    tokens_in: raw.tokens_in ?? raw.prompt_tokens ?? null,
    tokens_out: raw.tokens_out ?? raw.completion_tokens ?? null,
    cost_usd: raw.cost_usd ?? null,
    diff_content: raw.diff_content ?? raw.diff ?? "",
    gate_results,
    findings,
  };
}

// ---------------------------------------------------------------------------
// Public API Functions (Resilient: attempts backend, falls back to mock)
// ---------------------------------------------------------------------------

export async function getJobs(): Promise<Job[]> {
  try {
    const res = await fetch(`${API_BASE}/jobs`, { cache: "no-store", signal: AbortSignal.timeout(1500) });
    if (res.ok) {
      const data = await res.json();
      const rawList = Array.isArray(data) ? data : (data.jobs || []);
      if (rawList.length > 0) {
        return rawList.map(normalizeJob);
      }
    }
  } catch {
    // Backend offline or unreachable — use simulation
  }

  const now = Date.now();
  return [...sim.map((s) => viewOf(s, now)).reverse(), ...seed];
}

export async function getJob(id: string): Promise<Job | null> {
  try {
    const res = await fetch(`${API_BASE}/jobs/${id}`, { cache: "no-store", signal: AbortSignal.timeout(1500) });
    if (res.ok) {
      const data = await res.json();
      return normalizeJob(data);
    }
  } catch {
    // Fallback to simulation
  }

  const now = Date.now();
  const simmed = sim.find((s) => s.final.job_id === id);
  if (simmed) return viewOf(simmed, now);
  const fromSeed = seed.find((j) => j.job_id === id);
  return fromSeed ? normalizeJob(fromSeed) : null;
}

function extractDiffFiles(diff: string): string[] {
  const matches = Array.from(diff.matchAll(/^\+\+\+ (?:b\/)?(.+)$/gm));
  if (matches.length > 0) {
    return matches.map((m) => m[1].trim());
  }
  return ["utils.py"];
}

export async function submitPR(p: SubmitPayload): Promise<void> {
  // Always update local simulation
  submitMock(p);

  // If live backend is available, also submit to it
  try {
    const files = p.files && p.files.length > 0 ? p.files : extractDiffFiles(p.diff_content);
    await fetch(`${API_BASE}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pr_number: parseInt(p.pr_number, 10) || 101,
        title: p.title || `PR #${p.pr_number}: Update changes`,
        commit_sha: p.commit_sha,
        diff: p.diff_content,
        files: files,
      }),
      signal: AbortSignal.timeout(3000),
    });
  } catch {
    // Handled in mock state
  }
}
