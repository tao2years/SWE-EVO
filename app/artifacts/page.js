import ArtifactViewer from "@/components/artifact-viewer";
import { readArtifactForView } from "@/lib/dashboard-data";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function ArtifactsPage({ searchParams }) {
  const params = await searchParams;
  const relativePath = typeof params?.path === "string" ? params.path : "";
  const artifact = relativePath ? await readArtifactForView(relativePath) : null;
  return <ArtifactViewer artifact={artifact} />;
}
