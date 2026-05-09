import { readArtifact } from "@/lib/dashboard-data";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request) {
  const url = new URL(request.url);
  const relativePath = url.searchParams.get("path");
  if (!relativePath) {
    return Response.json(
      { error: "Missing artifact path" },
      {
        status: 400,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  const artifact = await readArtifact(relativePath);
  if (!artifact) {
    return Response.json(
      { error: "Artifact not found" },
      {
        status: 404,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  return new Response(artifact.content, {
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": artifact.contentType,
      "Content-Disposition": `inline; filename="${artifact.filename}"`,
    },
  });
}
