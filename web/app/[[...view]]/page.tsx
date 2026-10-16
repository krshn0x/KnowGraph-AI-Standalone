import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function Page({ params }: { params: Promise<{ view?: string[] }> }) {
  const { view = [] } = await params;
  if (view.length > 1 || (view.length && !["investigations", "ask", "experts", "documents", "graph", "sources"].includes(view[0]))) {
    notFound();
  }
  return null;
}
