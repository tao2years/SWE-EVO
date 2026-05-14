import CompareRunPage from "@/components/compare-run-page";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function CompareRunRoute({ params }) {
  const { compareId } = await params;
  return <CompareRunPage compareId={compareId} />;
}
