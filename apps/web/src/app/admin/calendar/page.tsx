import { redirect } from "next/navigation";
import { requireAdministrator } from "@/portals/admin/server";
import { administrationRequest } from "@/shared/api/account-administration";
import { AccountDenied } from "@/shared/api/account-entry";
import { CompanyCalendarDocument } from "@/shared/api/generated";
import { CalendarEditor } from "@/portals/admin/calendar-editor";
export default async function Calendar() {
  const { session } = await requireAdministrator();
  let result;
  try {
    result = await administrationRequest(session, CompanyCalendarDocument, {});
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    return (
      <>
        <h1>Working calendar</h1>
        <p role="alert">
          Calendar services are unavailable. Please try again later.
        </p>
      </>
    );
  }
  return (
    <>
      <p className="admin-eyebrow">COMPANY WORKING CALENDAR</p>
      <h1>Working calendar</h1>
      <p className="admin-intro">
        Set company working days, hours and special dates. Published versions
        preserve how deadlines were calculated.
      </p>
      <CalendarEditor workspace={result.companyCalendar} />
    </>
  );
}
