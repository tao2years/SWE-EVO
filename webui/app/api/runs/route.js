import { scanRuns } from "@/lib/dashboard-data";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  const payload = await scanRuns();
  return Response.json(payload, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
