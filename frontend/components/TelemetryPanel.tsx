import type { Job } from "@/lib/api";
import { DollarSign, Clock, Cpu, Repeat, ShieldAlert } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  icon: React.ReactNode;
  accent: "indigo" | "emerald" | "amber" | "cyan" | "rose";
}

const ACCENT_STYLES = {
  indigo: "from-indigo-500/20 to-purple-500/5 text-indigo-400 border-indigo-500/30",
  emerald: "from-emerald-500/20 to-teal-500/5 text-emerald-400 border-emerald-500/30",
  amber: "from-amber-500/20 to-orange-500/5 text-amber-400 border-amber-500/30",
  cyan: "from-cyan-500/20 to-blue-500/5 text-cyan-400 border-cyan-500/30",
  rose: "from-rose-500/20 to-pink-500/5 text-rose-400 border-rose-500/30",
};

function MetricCard({ label, value, sub, icon, accent }: MetricCardProps) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 backdrop-blur-sm transition-all duration-200 hover:border-slate-700 hover:shadow-lg hover:shadow-slate-900/50">
      <div className={`absolute top-0 right-0 h-16 w-16 bg-gradient-to-br ${ACCENT_STYLES[accent]} opacity-40 blur-xl pointer-events-none`} />
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {label}
        </span>
        <div className={`p-1.5 rounded-lg border bg-slate-800/60 ${ACCENT_STYLES[accent]}`}>
          {icon}
        </div>
      </div>
      <div className="mt-3 text-2xl font-bold tracking-tight text-white font-mono">
        {value}
      </div>
      {sub && (
        <div className="mt-1 text-xs text-slate-400 font-medium">
          {sub}
        </div>
      )}
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
      <MetricCard
        label="Total Spend"
        value={`$${totalCost.toFixed(4)}`}
        sub="LLM API cost"
        icon={<DollarSign className="h-4 w-4" />}
        accent="emerald"
      />
      <MetricCard
        label="Avg Latency"
        value={avgLatency != null ? `${avgLatency} ms` : "—"}
        sub={`over ${timed.length} completed`}
        icon={<Clock className="h-4 w-4" />}
        accent="cyan"
      />
      <MetricCard
        label="Tokens In / Out"
        value={`${tokensIn.toLocaleString()} / ${tokensOut.toLocaleString()}`}
        sub="Surgically bounded"
        icon={<Cpu className="h-4 w-4" />}
        accent="indigo"
      />
      <MetricCard
        label="Cache Hit Rate"
        value={hitRate != null ? `${hitRate}%` : "—"}
        sub={`${cacheHits} instant 0-token hits`}
        icon={<Repeat className="h-4 w-4" />}
        accent="amber"
      />
      <MetricCard
        label="Gate Rejections"
        value={String(gateRejected)}
        sub="100% cost saved ($0)"
        icon={<ShieldAlert className="h-4 w-4" />}
        accent="rose"
      />
    </div>
  );
}
