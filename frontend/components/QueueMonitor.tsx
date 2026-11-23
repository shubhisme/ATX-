"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getJobs, type Job } from "@/lib/api";
import StatusBadge from "./StatusBadge";
import DiffPreview from "./DiffPreview";
import TelemetryPanel from "./TelemetryPanel";

const WORKER_COUNT = 3;
const POLL_MS = 2000;
const HOVER_DELAY_MS = 300;
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
        <div className="space-y-4">
        <div className="grid grid-cols-3 gap-4">
        <div className="rounded border p-4">
        <div className="text-sm text-gray-500">Queue depth</div>
        <div className="text-2xl font-semibold">{queued}</div>
        </div>
        <div className="rounded border p-4">
        <div className="text-sm text-gray-500">Workers busy</div>
        <div className="text-2xl font-semibold">
        {reviewing} / {WORKER_COUNT}
        </div>
        <div className="mt-2 h-2 rounded bg-gray-200">
        <div
        className="h-2 rounded bg-blue-500"
        style={{ width: `${busyPct}%` }}
        />
        </div>
        </div>
        <div className="rounded border p-4">
        <div className="text-sm text-gray-500">Total jobs</div>
        <div className="text-2xl font-semibold">{jobs.length}</div>
        </div>
        </div>

        <TelemetryPanel jobs={jobs} />

        {error && (
            <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
            </div>
        )}

        <table className="w-full border-collapse text-sm">
        <thead>
        <tr className="border-b text-left text-gray-500">
        <th className="p-2">Job</th>
        <th className="p-2">PR</th>
        <th className="p-2">Commit</th>
        <th className="p-2">Status</th>
        <th className="p-2">Latency</th>
        <th className="p-2">Tokens in/out</th>
        <th className="p-2">Cost</th>
        <th className="p-2">Cache</th>
        </tr>
        </thead>
        <tbody>
        {jobs.map((j) => (
            <tr
            key={j.job_id}
            className="border-b hover:bg-gray-50"
            onMouseEnter={(e) => handleEnter(e, j.job_id)}
            onMouseLeave={handleLeave}
            >
            <td className="p-2">
            <Link href={`/pr/${j.job_id}`} className="text-blue-600 hover:underline">
            {j.job_id}
            </Link>
            </td>
            <td className="p-2">#{j.pr_number}</td>
            <td className="p-2 font-mono">{j.commit_sha.slice(0, 7)}</td>
            <td className="p-2">
            <StatusBadge status={j.status} />
            </td>
            <td className="p-2">{j.latency_ms != null ? `${j.latency_ms} ms` : "—"}</td>
            <td className="p-2">
            {j.tokens_in != null ? `${j.tokens_in} / ${j.tokens_out}` : "—"}
            </td>
            <td className="p-2">
            {j.cost_usd != null ? `$${j.cost_usd.toFixed(4)}` : "—"}
            </td>
            <td className="p-2">
            {j.cache_hit && (
                <span className="rounded bg-purple-100 px-2 py-0.5 text-xs text-purple-700">
                CACHE HIT
                </span>
            )}
            </td>
            </tr>
        ))}
        </tbody>
        </table>

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
