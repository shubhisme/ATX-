import BatchSimulator from "@/components/BatchSimulator";
import QueueMonitor from "@/components/QueueMonitor";
import { GitPullRequest, Activity, ShieldCheck, Zap } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md sticky top-0 z-40">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 ring-1 ring-white/20">
              <GitPullRequest className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight text-white">
                  PR Verification Engine
                </h1>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live Pool
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Group 2 • High-Throughput Context & Gate Verification Platform
              </p>
            </div>
          </div>

          {/* Quick Architecture Pill Badges */}
          <div className="flex items-center gap-2 text-xs font-medium">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300">
              <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
              Pre-LLM Gates &lt;1ms
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300">
              <Zap className="h-3.5 w-3.5 text-amber-400" />
              Surgical AST Context
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300">
              <Activity className="h-3.5 w-3.5 text-indigo-400" />
              3 Async Workers
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto max-w-7xl px-4 sm:px-6 py-8 space-y-8">
        {/* Simulator Card */}
        <section>
          <BatchSimulator />
        </section>

        {/* Live Queue & PR Table */}
        <section>
          <QueueMonitor />
        </section>
      </main>
    </div>
  );
}
