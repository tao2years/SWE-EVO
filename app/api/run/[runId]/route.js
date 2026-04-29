import { buildRunDetail, updateRunDisplayName } from "@/lib/dashboard-data";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(_request, { params }) {
  const { runId } = await params;
  const detail = await buildRunDetail(runId);
  if (!detail) {
    return Response.json(
      { error: "run not found" },
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

export async function PATCH(request, { params }) {
  const { runId } = await params;
  let payload = {};
  try {
    payload = await request.json();
  } catch {
    payload = {};
  }

  const detail = await updateRunDisplayName(runId, payload?.display_name);
  if (!detail) {
    return Response.json(
      { error: "run not found" },
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
