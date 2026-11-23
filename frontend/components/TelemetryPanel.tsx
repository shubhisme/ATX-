import type { Job } from "@/lib/api";

function Card({ label, value, sub }: { label: string; value: string; sub?: string }) {
    return (
        <div className="rounded border p-4">
        <div className="text-sm text-gray-500">{label}</div>
        <div className="text-2xl font-semibold">{value}</div>
        {sub && <div className="mt-1 text-xs text-gray-400">{sub}</div>}
        </div>
    );
}

export default function TelemetryPanel({ jobs }: { jobs: Job[] }) {
    const totalCost = jobs.reduce((sum, j) => sum + (j.cost_usd ?? 0), 0);
    const tokensIn = jobs.reduce((sum, j) => sum + (j.tokens_in ?? 0), 0);
    const tokensOut = jobs.reduce((sum, j) => sum + (j.tokens_out ?? 0), 0);

    const timed = jobs.filter((j) => j.latency_ms != null);
    const avgLatency = timed.length
    ? Math.round(timed.reduce((sum, j) => sum + (j.latency_ms ?? 0), 0) / timed.length)
    : null;

    const completed = jobs.filter((j) => j.status === "COMPLETED");
    const cacheHits = completed.filter((j) => j.cache_hit).length;
    const hitRate = completed.length
    ? Math.round((cacheHits / completed.length) * 100)
    : null;

    const gateRejected = jobs.filter((j) => j.status === "STATIC_FAILED").length;

    return (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <Card label="Total cost" value={`$${totalCost.toFixed(4)}`} />
        <Card
        label="Avg latency"
        value={avgLatency != null ? `${avgLatency} ms` : "—"}
        sub={`over ${timed.length} job${timed.length === 1 ? "" : "s"}`}
        />
        <Card
        label="Tokens in / out"
        value={`${tokensIn} / ${tokensOut}`}
        />
        <Card
        label="Cache hit rate"
        value={hitRate != null ? `${hitRate}%` : "—"}
        sub={`${cacheHits} of ${completed.length} completed`}
        />
        <Card
        label="Gate rejections"
        value={String(gateRejected)}
        sub="zero LLM spend"
        />
        </div>
    );
}
