"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getJobs, type Job } from "@/lib/api";
import StatusBadge from "./StatusBadge";
import DiffPreview from "./DiffPreview";
import TelemetryPanel from "./TelemetryPanel";
import { Users, Inbox, ArrowUpRight, CheckCircle2, Zap } from "lucide-react";

const WORKER_COUNT = 3;
const POLL_MS = 1500;
const HOVER_DELAY_MS = 250;
const CARD_HEIGHT = 270;

interface HoverState {
  id: string;
  left: number;
  top?: number;
  bottom?: number;
}

export default function QueueMonitor() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<HoverState | null>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await getJobs();
        if (active) {
          setJobs(data);
          setError(null);
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load jobs");
      }
    };
    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      active = false;
      clearInterval(timer);
      if (hoverTimer.current) clearTimeout(hoverTimer.current);
    };
  }, []);

  const handleEnter = (e: React.MouseEvent<HTMLTableRowElement>, id: string) => {
    const rect = e.currentTarget.getBoundingClientRect();
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => {
      const left = Math.max(8, Math.min(rect.left + 40, window.innerWidth - 464));
      const roomAbove = rect.top > CARD_HEIGHT + 8;
      setHover(
        roomAbove
          ? { id, left, bottom: window.innerHeight - rect.top + 4 }
          : { id, left, top: rect.bottom + 4 }
      );
    }, HOVER_DELAY_MS);
  };

  const handleLeave = () => {
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    setHover(null);
  };

  const hoveredJob = hover ? jobs.find((j) => j.job_id === hover.id) : undefined;

  const reviewing = jobs.filter((j) => j.status === "AI_REVIEWING").length;
  const queued = jobs.filter((j) => j.status === "QUEUED").length;
  const busyPct = Math.min(100, (reviewing / WORKER_COUNT) * 100);

  return (
    <div className="space-y-6">
      {/* Worker Pool & Queue Metrics Header */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-md">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider">
            <span>Async Queue Depth</span>
            <Inbox className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-white">
            {queued}
            <span className="text-xs font-normal text-slate-400 ml-2">pending in queue</span>
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-md">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider">
            <span>Active Worker Pool</span>
            <Users className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-white">
            {reviewing} <span className="text-base text-slate-400 font-normal">/ {WORKER_COUNT} busy</span>
          </div>
          <div className="mt-2 h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-300"
              style={{ width: `${busyPct}%` }}
            />
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-md">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider">
            <span>Total Evaluated PRs</span>
            <CheckCircle2 className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-white">
            {jobs.length}
            <span className="text-xs font-normal text-slate-400 ml-2">lifetime events</span>
          </div>
        </div>
      </div>

      {/* Aggregate Telemetry Panel */}
      <TelemetryPanel jobs={jobs} />

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
          {error}
        </div>
      )}

      {/* Modern Operations Table */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-md overflow-hidden shadow-xl shadow-slate-950/40">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-white">Live PR Verification Queue</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Hover over any row to preview unified diff & inline review comments.
            </p>
          </div>
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            Polling live
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800/80 bg-slate-950/40 text-slate-400 font-semibold uppercase tracking-wider">
                <th className="py-3 px-4">Job ID</th>
                <th className="py-3 px-4">PR #</th>
                <th className="py-3 px-4">Commit SHA</th>
                <th className="py-3 px-4">State</th>
                <th className="py-3 px-4 text-right">Latency</th>
                <th className="py-3 px-4 text-right">Tokens (In / Out)</th>
                <th className="py-3 px-4 text-right">Cost (USD)</th>
                <th className="py-3 px-4 text-center">Cache</th>
                <th className="py-3 px-4 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    No pull requests in queue. Fire PRs using the simulator above.
                  </td>
                </tr>
              ) : (
                jobs.map((j) => (
                  <tr
                    key={j.job_id}
                    className="hover:bg-slate-800/40 transition-colors cursor-pointer group"
                    onMouseEnter={(e) => handleEnter(e, j.job_id)}
                    onMouseLeave={handleLeave}
                  >
                    <td className="py-3.5 px-4 font-mono font-medium text-slate-300">
                      <Link
                        href={`/pr/${j.job_id}`}
                        className="text-indigo-400 hover:text-indigo-300 hover:underline"
                      >
                        {j.job_id.slice(0, 12)}
                      </Link>
                    </td>
                    <td className="py-3.5 px-4 font-bold text-white">
                      #{j.pr_number}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-400">
                      {j.commit_sha.slice(0, 7)}
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={j.status} />
                    </td>
                    <td className="py-3.5 px-4 text-right font-mono text-slate-300">
                      {j.latency_ms != null ? `${j.latency_ms} ms` : "—"}
                    </td>
                    <td className="py-3.5 px-4 text-right font-mono text-slate-300">
                      {j.tokens_in != null ? (
                        <span>
                          {j.tokens_in.toLocaleString()} / {j.tokens_out?.toLocaleString()}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right font-mono font-semibold text-emerald-400">
                      {j.cost_usd != null ? `$${j.cost_usd.toFixed(4)}` : "—"}
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      {j.cache_hit ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 text-xs font-semibold text-amber-300">
                          <Zap className="h-3 w-3" />
                          HIT
                        </span>
                      ) : (
                        <span className="text-slate-600 text-xs">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <Link
                        href={`/pr/${j.job_id}`}
                        className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 hover:text-white transition-colors"
                      >
                        Details
                        <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {hover && hoveredJob && (
        <DiffPreview
          job={hoveredJob}
          left={hover.left}
          top={hover.top}
          bottom={hover.bottom}
        />
      )}
    </div>
  );
}
