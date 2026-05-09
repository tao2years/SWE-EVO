import { updateAnalysisReview } from "@/lib/dashboard-data";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function PATCH(request, { params }) {
  const { instanceId } = await params;
  let payload = {};
  try {
    payload = await request.json();
  } catch {
    payload = {};
  }

  const reviewed = Boolean(payload?.reviewed);
  const result = await updateAnalysisReview(instanceId, reviewed);
  if (!result) {
    return Response.json(
      { error: "analysis report not found" },
      {
        status: 404,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  return Response.json(result, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
