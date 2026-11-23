import type { JobStatus } from "@/lib/api";

const CONFIG: Record<
  JobStatus,
  { label: string; badge: string; dot: string; pulse?: boolean }
> = {
  QUEUED: {
    label: "QUEUED",
    badge: "bg-slate-800 text-slate-300 border-slate-700",
    dot: "bg-slate-400",
  },
  AI_REVIEWING: {
    label: "AI REVIEWING",
    badge: "bg-sky-500/10 text-sky-400 border-sky-500/30",
    dot: "bg-sky-400",
    pulse: true,
  },
  COMPLETED: {
    label: "COMPLETED",
    badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    dot: "bg-emerald-400",
  },
  STATIC_FAILED: {
    label: "STATIC FAILED",
    badge: "bg-rose-500/10 text-rose-400 border-rose-500/30",
    dot: "bg-rose-400",
  },
  SUPERSEDED: {
    label: "SUPERSEDED",
    badge: "bg-amber-500/10 text-amber-400 border-amber-500/30 opacity-70",
    dot: "bg-amber-400",
  },
};

export default function StatusBadge({ status }: { status: JobStatus }) {
  const conf = CONFIG[status] || {
    label: status,
    badge: "bg-slate-800 text-slate-300 border-slate-700",
    dot: "bg-slate-400",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-wide ${conf.badge}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${conf.dot} ${
          conf.pulse ? "animate-ping" : ""
        }`}
      />
      {conf.label}
    </span>
  );
}
