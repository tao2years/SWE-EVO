import { buildCompareRunsOverview } from "@/lib/dashboard-data";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  const payload = await buildCompareRunsOverview();
  return Response.json(payload, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
