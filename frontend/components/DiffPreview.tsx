import type { Job } from "@/lib/api";

const MAX_LINES = 10;

function lineStyle(text: string): string {
    if (text.startsWith("+++") || text.startsWith("---")) return "text-gray-500";
    if (text.startsWith("@@")) return "bg-blue-50 text-blue-700";
    if (text.startsWith("+")) return "bg-green-50 text-green-800";
    if (text.startsWith("-")) return "bg-red-50 text-red-800";
    return "text-gray-700";
}

export default function DiffPreview({
    job,
    left,
    top,
    bottom,
}: {
    job: Job;
    left: number;
    top?: number;
    bottom?: number;
}) {
    const all = job.diff_content.split("\n");
    const shown = all.slice(0, MAX_LINES);
    const hidden = all.length - shown.length;

    return (
        <div
        className="pointer-events-none fixed z-50 w-[28rem] rounded border border-gray-300 bg-white shadow-lg"
        style={{ left, top, bottom }}
        >
        <div className="flex items-center justify-between border-b px-3 py-1.5 text-xs text-gray-500">
        <span>
        {job.job_id} · PR #{job.pr_number}
        </span>
        <span>
        {job.findings.length} finding{job.findings.length === 1 ? "" : "s"}
        </span>
        </div>
        <div className="flex items-center gap-4 border-b bg-gray-50 px-3 py-1.5 text-xs text-gray-600">
        <span>{job.latency_ms != null ? `${job.latency_ms} ms` : "— ms"}</span>
        <span>
        {job.tokens_in != null ? `${job.tokens_in} / ${job.tokens_out} tok` : "— tok"}
        </span>
        <span>{job.cost_usd != null ? `$${job.cost_usd.toFixed(4)}` : "— $"}</span>
        {job.cache_hit && (
            <span className="rounded bg-purple-100 px-1.5 py-0.5 text-purple-700">
            CACHE HIT
            </span>
        )}
        </div>
        <div className="overflow-hidden py-1 font-mono text-xs">
        {shown.map((text, i) => (
            <div key={i} className={`whitespace-pre px-3 ${lineStyle(text)}`}>
            {text || " "}
            </div>
        ))}
        {hidden > 0 && (
            <div className="px-3 pt-1 text-gray-400">… {hidden} more lines</div>
        )}
        </div>
        <div className="border-t px-3 py-1 text-xs text-gray-400">
        Click the job for the full diff
        </div>
        </div>
    );
}
