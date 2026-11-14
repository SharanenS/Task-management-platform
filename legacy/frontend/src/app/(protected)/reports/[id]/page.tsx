import { ReportDetail } from "@/features/reports/report-detail";

export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <ReportDetail id={(await params).id} />;
}
