import PRDetail from "@/components/PRDetail";

export default async function PRPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = await params;
    return (
        <main className="mx-auto max-w-6xl space-y-6 p-6">
        <PRDetail id={id} />
        </main>
    );
}
