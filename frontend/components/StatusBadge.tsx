import type { JobStatus } from "@/lib/api";

const STYLES: Record<JobStatus, string> = {
    QUEUED: "bg-gray-100 text-gray-700 border-gray-300",
    AI_REVIEWING: "bg-blue-100 text-blue-700 border-blue-300",
    COMPLETED: "bg-green-100 text-green-700 border-green-300",
    STATIC_FAILED: "bg-red-100 text-red-700 border-red-300",
    SUPERSEDED: "bg-yellow-100 text-yellow-700 border-yellow-300",
};

export default function StatusBadge({ status }: { status: JobStatus }) {
    return (
        <span
        className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}
        >
        {status}
        </span>
    );
}
