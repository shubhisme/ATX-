"use client";

import { useRef, useState } from "react";
import { submitPR, type SubmitPayload } from "@/lib/api";
import { CLEAN_SAMPLES, SECRET_SAMPLE, type Sample } from "@/lib/samples";
import { Play, Sparkles, ShieldAlert, Layers, Flame, CheckCircle2 } from "lucide-react";

const randomSha = () =>
  Array.from({ length: 40 }, () => Math.floor(Math.random() * 16).toString(16)).join("");

const pick = <T,>(items: T[]): T => items[Math.floor(Math.random() * items.length)];

export default function BatchSimulator() {
  const [count, setCount] = useState(5);
  const [reuse, setReuse] = useState(false);
  const [leak, setLeak] = useState(false);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const prCounter = useRef(200);

  const fireBatch = async (
    overrideCount?: number,
    overrideReuse?: boolean,
    overrideLeak?: boolean
  ) => {
    const batchSize = overrideCount ?? count;
    const isReuse = overrideReuse ?? reuse;
    const isLeak = overrideLeak ?? leak;

    setSending(true);
    setStatus(null);

    const reuseSha = randomSha();
    const reuseSample = pick(CLEAN_SAMPLES);

    const payloads: SubmitPayload[] = Array.from({ length: batchSize }, (_, i) => {
      let sample: Sample;
      let sha: string;
      if (isReuse) {
        sample = reuseSample;
        sha = reuseSha;
      } else if (isLeak && (batchSize === 1 || i % 3 === 0)) {
        sample = SECRET_SAMPLE;
        sha = randomSha();
      } else {
        sample = pick(CLEAN_SAMPLES);
        sha = randomSha();
      }
      prCounter.current += 1;
      return {
        repo_url: "sample_repo",
        pr_number: String(prCounter.current),
        commit_sha: sha,
        diff_content: sample.diff,
        title: `PR #${prCounter.current}: ${sample.label}`,
        files: sample.files || ["utils.py"],
      };
    });

    try {
      const t0 = performance.now();
      const results = await Promise.allSettled(payloads.map((p) => submitPR(p)));
      const ms = Math.round(performance.now() - t0);
      const failed = results.filter((r) => r.status === "rejected").length;
      setStatus(
        failed > 0
          ? `Dispatched ${batchSize - failed}/${batchSize} PRs (${failed} failed, ${ms}ms)`
          : `Dispatched ${batchSize} PR${batchSize === 1 ? "" : "s"} concurrently in ${ms}ms`
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-md shadow-xl shadow-slate-950/50">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-800/80">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Flame className="h-5 w-5 text-amber-400" />
              Batch PR Concurrency Simulator
            </h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
              asyncio.Queue Stress
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Inject realistic synthetic PR diffs into the worker queue to demonstrate concurrency, gates, and caching.
          </p>
        </div>

        {/* 1-Click Demo Presets */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => fireBatch(1, false, false)}
            disabled={sending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/20 transition-all disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
            +1 Clean PR
          </button>
          <button
            onClick={() => fireBatch(1, false, true)}
            disabled={sending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-500/10 text-rose-300 border border-rose-500/30 hover:bg-rose-500/20 transition-all disabled:opacity-50"
          >
            <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
            +1 Secret Leak ($0)
          </button>
          <button
            onClick={() => fireBatch(2, true, false)}
            disabled={sending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30 hover:bg-amber-500/20 transition-all disabled:opacity-50"
          >
            <Layers className="h-3.5 w-3.5 text-amber-400" />
            Cache Hit Test
          </button>
          <button
            onClick={() => fireBatch(20, false, false)}
            disabled={sending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-purple-500/20 text-purple-200 border border-purple-500/40 hover:bg-purple-500/30 transition-all disabled:opacity-50 shadow-sm shadow-purple-500/20"
          >
            <Flame className="h-3.5 w-3.5 text-purple-400" />
            Burst 20 PRs
          </button>
        </div>
      </div>

      {/* Manual Controls */}
      <div className="mt-5 flex flex-wrap items-center justify-between gap-6">
        <div className="flex flex-wrap items-center gap-6">
          <label className="flex items-center gap-3 text-sm">
            <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">
              Volume:
            </span>
            <input
              type="range"
              min={1}
              max={20}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              disabled={sending}
              className="h-2 w-32 md:w-44 appearance-none rounded-lg bg-slate-800 accent-indigo-500 cursor-pointer"
            />
            <span className="font-mono text-sm font-bold text-white bg-slate-800 px-2 py-0.5 rounded border border-slate-700 min-w-8 text-center">
              {count}
            </span>
          </label>

          <label className="flex items-center gap-2 text-xs font-medium text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={reuse}
              onChange={(e) => setReuse(e.target.checked)}
              disabled={sending}
              className="rounded border-slate-700 bg-slate-800 text-indigo-500 focus:ring-0 focus:ring-offset-0"
            />
            Deduplication Test (Reuse SHA)
          </label>

          <label
            className={`flex items-center gap-2 text-xs font-medium cursor-pointer ${
              reuse ? "text-slate-500" : "text-slate-300"
            }`}
          >
            <input
              type="checkbox"
              checked={leak && !reuse}
              onChange={(e) => setLeak(e.target.checked)}
              disabled={sending || reuse}
              className="rounded border-slate-700 bg-slate-800 text-rose-500 focus:ring-0 focus:ring-offset-0"
            />
            Inject Secret Leaks (Every 3rd)
          </label>
        </div>

        <div className="flex items-center gap-3">
          {status && (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {status}
            </span>
          )}

          <button
            onClick={() => fireBatch()}
            disabled={sending}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 px-5 py-2 text-sm font-bold text-white shadow-lg shadow-indigo-500/25 hover:from-indigo-600 hover:to-purple-700 transition-all active:scale-95 disabled:opacity-50"
          >
            <Play className={`h-4 w-4 ${sending ? "animate-spin" : "fill-current"}`} />
            {sending ? "Dispatching..." : `Fire ${count} PRs`}
          </button>
        </div>
      </div>
    </div>
  );
}
