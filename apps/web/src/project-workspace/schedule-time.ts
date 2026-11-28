/** Display scheduling instants in the pinned project timezone, not the viewer's zone. */
export function scheduleTime(
  value: string | null | undefined,
  timezone: string,
) {
  return value
    ? new Intl.DateTimeFormat("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: timezone,
      }).format(new Date(value))
    : "Unknown";
}
