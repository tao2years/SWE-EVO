import { buildCaseTraceDetail } from "@/lib/dashboard-data";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(_request, { params }) {
  const { runId, instanceId } = await params;
  const detail = await buildCaseTraceDetail(runId, instanceId);
  if (!detail) {
    return Response.json(
      { error: "trace not found" },
      {
        status: 404,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  return Response.json(detail, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
