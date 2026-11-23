import PRDetail from "@/components/PRDetail";

export default async function PRPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100 py-8 px-4 sm:px-6">
      <PRDetail id={id} />
    </div>
  );
}
