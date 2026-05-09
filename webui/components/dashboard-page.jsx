import DashboardClient from "@/components/dashboard-client";
import { buildInitialDashboardData } from "@/lib/dashboard-data";

export default async function DashboardPage() {
  const initialData = await buildInitialDashboardData();
  return <DashboardClient initialData={initialData} />;
}
