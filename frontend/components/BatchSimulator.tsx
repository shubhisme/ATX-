"use client";

import { useRef, useState } from "react";
import { submitPR, type SubmitPayload } from "@/lib/api";
import { CLEAN_SAMPLES, SECRET_SAMPLE, type Sample } from "@/lib/samples";

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

    const fire = async () => {
        setSending(true);
        setStatus(null);

        const reuseSha = randomSha();
        const reuseSample = pick(CLEAN_SAMPLES);

        const payloads: SubmitPayload[] = Array.from({ length: count }, (_, i) => {
            let sample: Sample;
            let sha: string;
            if (reuse) {
                sample = reuseSample;
                sha = reuseSha;
            } else {
                sample = leak && i % 3 === 1 ? SECRET_SAMPLE : pick(CLEAN_SAMPLES);
                sha = randomSha();
            }
            prCounter.current += 1;
            return {
                repo_url: "sample_repo",
                pr_number: String(prCounter.current),
                                                     commit_sha: sha,
                                                     diff_content: sample.diff,
            };
        });

        try {
            const t0 = performance.now();
            const results = await Promise.allSettled(payloads.map((p) => submitPR(p)));
            const ms = Math.round(performance.now() - t0);
            const failed = results.filter((r) => r.status === "rejected").length;
            setStatus(
                failed > 0
                ? `Submitted ${count - failed} of ${count} PRs, ${failed} failed (${ms} ms)`
                : `Submitted ${count} PR${count === 1 ? "" : "s"} in ${ms} ms`
            );
        } finally {
            setSending(false);
        }
    };

    return (
        <div className="rounded border p-4">
        <div className="mb-3 font-medium">Batch PR Simulator</div>

        <div className="flex flex-wrap items-center gap-6">
        <label className="flex items-center gap-3 text-sm">
        <span className="text-gray-600">PRs to send</span>
        <input
        type="range"
        min={1}
        max={20}
        value={count}
        onChange={(e) => setCount(Number(e.target.value))}
        disabled={sending}
        className="w-40"
        />
        <span className="w-6 text-right font-semibold">{count}</span>
        </label>

        <label className="flex items-center gap-2 text-sm">
        <input
        type="checkbox"
        checked={reuse}
        onChange={(e) => setReuse(e.target.checked)}
        disabled={sending}
        />
        Reuse same commit (cache test)
        </label>

        <label
        className={`flex items-center gap-2 text-sm ${reuse ? "text-gray-400" : ""}`}
        >
        <input
        type="checkbox"
        checked={leak && !reuse}
        onChange={(e) => setLeak(e.target.checked)}
        disabled={sending || reuse}
        />
        Include secret leaks (every third PR)
        </label>

        <button
        onClick={fire}
        disabled={sending}
        className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
        {sending ? "Sending…" : "Fire"}
        </button>

        {status && <span className="text-sm text-gray-600">{status}</span>}
        </div>
        </div>
    );
}
