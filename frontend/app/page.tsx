import BatchSimulator from "@/components/BatchSimulator";
import QueueMonitor from "@/components/QueueMonitor";

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
    <h1 className="text-2xl font-bold">PR Operations Dashboard</h1>
    <BatchSimulator />
    <QueueMonitor />
    </main>
  );
}
