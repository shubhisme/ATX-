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

// The payload shape is a guess until Shubh confirms POST /submit.
export interface SubmitPayload {
    repo_url: string;
    pr_number: string;
    commit_sha: string;
    diff_content: string;
}

// Flip to false once Shubh's backend is running.
const USE_MOCK = true;
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const seed = mock.jobs as unknown as Job[];

// ---------------------------------------------------------------------------
// Mock mode: simulates submitted PRs moving through a 3-worker queue.
// State lives in browser memory and resets on page reload.
// ---------------------------------------------------------------------------

const WORKERS = 3;
// Assumed prices (USD per token). The real cost calculation is the backend's job.
const INPUT_USD_PER_TOKEN = 0.15 / 1_000_000;
const OUTPUT_USD_PER_TOKEN = 0.6 / 1_000_000;

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

function submitMock(p: SubmitPayload): void {
    const now = Date.now();
    simCounter += 1;

    const base: Job = {
        job_id: `sim-${String(simCounter).padStart(3, "0")}`,
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

    const sample = findSample(p.diff_content);
    const findings = sample ? sample.findings.map((f) => ({ ...f })) : [];

    // 1. Cache check first: a known SHA returns instantly with 0 tokens.
    if (seenShas.has(p.commit_sha)) {
        sim.push({
            kind: "instant",
            startAt: now,
            endAt: now,
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
                 findings,
            },
        });
        return;
    }

    // 2. Deterministic gate: a leaked key stops the PR with zero LLM spend.
    if (/AKIA[0-9A-Z]{16}/.test(p.diff_content)) {
        sim.push({
            kind: "instant",
            startAt: now,
            endAt: now,
            final: {
                ...base,
                status: "STATIC_FAILED",
                started_at: now / 1000,
                completed_at: (now + 40) / 1000,
                 latency_ms: 40,
                 tokens_in: 0,
                 tokens_out: 0,
                 cost_usd: 0,
                 gate_results: [
                     {
                         check_type: "secrets",
                         status: "FAIL",
                         details: "AWS key pattern found in added lines",
                         duration_ms: rand(3, 9),
                     },
                 ],
            },
        });
        return;
    }

    // 3. Queue for the first free worker.
    const duration = rand(1500, 3500);
    const w = workerFree.indexOf(Math.min(...workerFree));
    const startAt = Math.max(now + 300, workerFree[w]);
    const endAt = startAt + duration;
    workerFree[w] = endAt;
    seenShas.add(p.commit_sha);

    const tokensIn = rand(1500, 3000);
    const tokensOut = rand(200, 500);

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
                { check_type: "secrets", status: "PASS", details: "", duration_ms: rand(3, 9) },
             { check_type: "syntax", status: "PASS", details: "", duration_ms: rand(6, 12) },
            ],
            findings,
        },
    });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function getJobs(): Promise<Job[]> {
    if (USE_MOCK) {
        const now = Date.now();
        return [...sim.map((s) => viewOf(s, now)).reverse(), ...seed];
    }
    const res = await fetch(`${API_BASE}/jobs`, { cache: "no-store" });
    if (!res.ok) throw new Error(`GET /jobs failed: ${res.status}`);
    return res.json();
}

export async function getJob(id: string): Promise<Job | null> {
    if (USE_MOCK) {
        const now = Date.now();
        const simmed = sim.find((s) => s.final.job_id === id);
        if (simmed) return viewOf(simmed, now);
        return seed.find((j) => j.job_id === id) ?? null;
    }
    const res = await fetch(`${API_BASE}/jobs/${id}`, { cache: "no-store" });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`GET /jobs/${id} failed: ${res.status}`);
    return res.json();
}

export async function submitPR(p: SubmitPayload): Promise<void> {
    if (USE_MOCK) {
        submitMock(p);
        return;
    }
    const res = await fetch(`${API_BASE}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(p),
    });
    if (!res.ok) throw new Error(`POST /submit failed: ${res.status}`);
}
