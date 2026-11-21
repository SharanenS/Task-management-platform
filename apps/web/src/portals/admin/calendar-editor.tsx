"use client";
import { useState } from "react";
import type {
  CompanyCalendarQuery,
  CalendarConfigurationInput,
  PreviewCompanyCalendarMutation,
  CalculateWorkingDaysQuery,
} from "@/shared/api/generated";
const weekdays = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];
type Workspace = CompanyCalendarQuery["companyCalendar"];
function editable(
  value: NonNullable<Workspace["current"]>["config"],
): CalendarConfigurationInput {
  return {
    timezone: value.timezone,
    week: value.week.map(({ weekday, working, opens, closes }) => ({
      weekday,
      working,
      opens,
      closes,
    })),
    holidays: value.holidays.map(({ date, label }) => ({ date, label })),
    exceptions: value.exceptions.map(
      ({ date, label, working, opens, closes }) => ({
        date,
        label,
        working,
        opens,
        closes,
      }),
    ),
  };
}
export function CalendarEditor({ workspace }: { workspace: Workspace }) {
  const [config, setConfig] = useState<CalendarConfigurationInput>(() =>
    workspace.current
      ? editable(workspace.current.config)
      : {
          timezone: "",
          week: weekdays.map((_, i) => ({
            weekday: i + 1,
            working: false,
            opens: null,
            closes: null,
          })),
          holidays: [],
          exceptions: [],
        },
  );
  const [preview, setPreview] = useState<
    PreviewCompanyCalendarMutation["previewCompanyCalendar"] | null
  >(null);
  const [confirmed, setConfirmed] = useState(false);
  const [publicationRequestId, setPublicationRequestId] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [calculation, setCalculation] = useState<
    CalculateWorkingDaysQuery["calculateWorkingDays"] | null
  >(null);
  function update(next: CalendarConfigurationInput) {
    setConfig(next);
    setPreview(null);
    setConfirmed(false);
    setMessage("");
  }
  async function command(action: string, input: unknown) {
    const response = await fetch("/admin/calendar/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, input }),
    });
    const value = await response.json();
    if (!response.ok)
      throw new Error(value.error ?? "Calendar service unavailable");
    return value.result;
  }
  async function action(work: () => Promise<void>) {
    setPending(true);
    setMessage("");
    try {
      await work();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Calendar service unavailable",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      {!workspace.current && (
        <p className="accounts-notice">
          No company calendar has been configured. Enter the actual company
          values. The first calendar uses this device’s local time
          automatically.
        </p>
      )}
      {message && (
        <p role="alert" className="accounts-notice">
          {message}
        </p>
      )}
      <section className="accounts-panel">
        <h2>
          {workspace.current
            ? `Edit from version ${workspace.current.number}`
            : "Configure the first calendar"}
        </h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void action(async () => {
              const timezone =
                config.timezone ||
                Intl.DateTimeFormat().resolvedOptions().timeZone;
              if (!timezone)
                throw new Error(
                  "Your device’s local time could not be detected. Check its date and time settings, then reload.",
                );
              const result = await command("preview", { ...config, timezone });
              setPreview(result);
              setPublicationRequestId(crypto.randomUUID());
              setConfirmed(false);
            });
          }}
        >
          <fieldset disabled={pending} className="calendar-fields">
            <p>
              Enter your company’s local working hours. Existing calendar time
              settings are retained when you publish a new version.
            </p>
            <h3>Weekly working hours</h3>
            <p>
              Enter hours only for working days. Overnight shifts and
              partial-day durations are not supported.
            </p>
            {config.week.map((row, i) => (
              <div className="calendar-weekday" key={row.weekday}>
                <label>
                  <input
                    type="checkbox"
                    checked={row.working}
                    onChange={(e) =>
                      update({
                        ...config,
                        week: config.week.map((r, j) =>
                          j === i
                            ? {
                                ...r,
                                working: e.target.checked,
                                opens: null,
                                closes: null,
                              }
                            : r,
                        ),
                      })
                    }
                  />
                  {weekdays[i]} working
                </label>
                <label>
                  Opens
                  <input
                    type="time"
                    aria-label={`${weekdays[i]} opens`}
                    disabled={!row.working}
                    required={row.working}
                    value={row.opens ?? ""}
                    onChange={(e) =>
                      update({
                        ...config,
                        week: config.week.map((r, j) =>
                          j === i ? { ...r, opens: e.target.value } : r,
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  Closes
                  <input
                    type="time"
                    aria-label={`${weekdays[i]} closes`}
                    disabled={!row.working}
                    required={row.working}
                    value={row.closes ?? ""}
                    onChange={(e) =>
                      update({
                        ...config,
                        week: config.week.map((r, j) =>
                          j === i ? { ...r, closes: e.target.value } : r,
                        ),
                      })
                    }
                  />
                </label>
              </div>
            ))}
            <h3>Holidays</h3>
            <p>
              Holidays close dates unless an explicit working exception reopens
              them.
            </p>
            {config.holidays.map((row, i) => (
              <div className="calendar-date" key={i}>
                <label>
                  Date
                  <input
                    type="date"
                    aria-label={`Holiday ${i + 1} date`}
                    min="1970-01-01"
                    max="2199-12-31"
                    required
                    value={row.date}
                    onChange={(e) =>
                      update({
                        ...config,
                        holidays: config.holidays.map((r, j) =>
                          j === i ? { ...r, date: e.target.value } : r,
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  Name
                  <input
                    aria-label={`Holiday ${i + 1} name`}
                    required
                    maxLength={150}
                    value={row.label}
                    onChange={(e) =>
                      update({
                        ...config,
                        holidays: config.holidays.map((r, j) =>
                          j === i ? { ...r, label: e.target.value } : r,
                        ),
                      })
                    }
                  />
                </label>
                <button
                  type="button"
                  aria-label={`Remove holiday ${i + 1}`}
                  onClick={() =>
                    update({
                      ...config,
                      holidays: config.holidays.filter((_, j) => j !== i),
                    })
                  }
                >
                  Remove
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() =>
                update({
                  ...config,
                  holidays: [...config.holidays, { date: "", label: "" }],
                })
              }
            >
              Add holiday
            </button>
            <h3>Special date exceptions</h3>
            <p>
              Exceptions override both the weekly pattern and holidays. Give
              each change a reason.
            </p>
            {config.exceptions.map((row, i) => (
              <div className="calendar-date" key={i}>
                <label>
                  Date
                  <input
                    type="date"
                    aria-label={`Exception ${i + 1} date`}
                    min="1970-01-01"
                    max="2199-12-31"
                    required
                    value={row.date}
                    onChange={(e) =>
                      update({
                        ...config,
                        exceptions: config.exceptions.map((r, j) =>
                          j === i ? { ...r, date: e.target.value } : r,
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  Reason
                  <input
                    aria-label={`Exception ${i + 1} reason`}
                    required
                    maxLength={150}
                    value={row.label}
                    onChange={(e) =>
                      update({
                        ...config,
                        exceptions: config.exceptions.map((r, j) =>
                          j === i ? { ...r, label: e.target.value } : r,
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={row.working}
                    onChange={(e) =>
                      update({
                        ...config,
                        exceptions: config.exceptions.map((r, j) =>
                          j === i
                            ? {
                                ...r,
                                working: e.target.checked,
                                opens: null,
                                closes: null,
                              }
                            : r,
                        ),
                      })
                    }
                  />
                  Working exception
                </label>
                {row.working && (
                  <>
                    <label>
                      Opens
                      <input
                        type="time"
                        aria-label={`Exception ${i + 1} opens`}
                        required
                        value={row.opens ?? ""}
                        onChange={(e) =>
                          update({
                            ...config,
                            exceptions: config.exceptions.map((r, j) =>
                              j === i ? { ...r, opens: e.target.value } : r,
                            ),
                          })
                        }
                      />
                    </label>
                    <label>
                      Closes
                      <input
                        type="time"
                        aria-label={`Exception ${i + 1} closes`}
                        required
                        value={row.closes ?? ""}
                        onChange={(e) =>
                          update({
                            ...config,
                            exceptions: config.exceptions.map((r, j) =>
                              j === i ? { ...r, closes: e.target.value } : r,
                            ),
                          })
                        }
                      />
                    </label>
                  </>
                )}
                <button
                  type="button"
                  aria-label={`Remove exception ${i + 1}`}
                  onClick={() =>
                    update({
                      ...config,
                      exceptions: config.exceptions.filter((_, j) => j !== i),
                    })
                  }
                >
                  Remove
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() =>
                update({
                  ...config,
                  exceptions: [
                    ...config.exceptions,
                    {
                      date: "",
                      label: "",
                      working: false,
                      opens: null,
                      closes: null,
                    },
                  ],
                })
              }
            >
              Add exception
            </button>
            <button className="admin-primary-button">
              Preview calendar changes
            </button>
          </fieldset>
        </form>
      </section>
      {preview && (
        <section className="accounts-panel" aria-labelledby="calendar-preview">
          <h2 id="calendar-preview">Review calendar changes</h2>
          <p>
            Based on version {preview.baseNumber}. Changed sections:{" "}
            {preview.changedSections.join(", ")}. The preview expires after ten
            minutes.
          </p>
          <p>
            Publishing creates a new immutable version. Existing commitments
            keep their original calendar version. Project schedule revision is
            introduced in a later stage; no existing schedules are rewritten
            here.
          </p>
          <p>
            Company local time: {preview.config.timezone}. Working days:{" "}
            {preview.config.week
              .filter((r) => r.working)
              .map((r) => `${weekdays[r.weekday - 1]} ${r.opens}–${r.closes}`)
              .join("; ")}
            .
          </p>
          <p>
            {preview.config.holidays.length} holidays;{" "}
            {preview.config.exceptions.length} exceptions.
          </p>
          <ul>
            {preview.config.holidays.map((row) => (
              <li key={row.date}>
                Holiday: {row.date} · {row.label}
              </li>
            ))}
            {preview.config.exceptions.map((row) => (
              <li key={row.date}>
                Exception: {row.date} · {row.label} ·{" "}
                {row.working ? `${row.opens}–${row.closes}` : "Non-working"}
              </li>
            ))}
          </ul>
          <label className="accounts-confirm">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            I confirm this calendar publication
          </label>
          <button
            disabled={pending || !confirmed}
            onClick={() =>
              void action(async () => {
                await command("publish", {
                  previewId: preview.previewId,
                  requestId: publicationRequestId,
                  confirm: true,
                });
                window.location.reload();
              })
            }
          >
            Publish calendar version
          </button>
        </section>
      )}
      <section className="accounts-panel">
        <h2>Published calendar history</h2>
        {workspace.history.length ? (
          <ul>
            {workspace.history.map((row) => (
              <li key={row.id}>
                Version {row.number} · {row.createdAt} · Administrator reference{" "}
                {row.actorId}
              </li>
            ))}
          </ul>
        ) : (
          <p>No published calendar versions.</p>
        )}
      </section>
      {workspace.current && (
        <section className="accounts-panel">
          <h2>Check working-day dates</h2>
          <p>
            Use a published version to check an example. This does not create a
            task, change a commitment or estimate employee capacity.
          </p>
          <form
            className="people-form"
            onSubmit={(e) => {
              e.preventDefault();
              const values = new FormData(e.currentTarget);
              void action(async () =>
                setCalculation(
                  await command("calculate", {
                    versionId: String(values.get("versionId")),
                    start: String(values.get("start")),
                    duration: Number(values.get("duration")),
                  }),
                ),
              );
            }}
          >
            <label>
              Calendar version
              <select
                name="versionId"
                aria-label="Calendar version"
                defaultValue={workspace.current.id}
              >
                {workspace.history.map((row) => (
                  <option key={row.id} value={row.id}>
                    Version {row.number}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Planned start
              <input
                name="start"
                type="date"
                min="1970-01-01"
                max="2199-12-31"
                required
              />
            </label>
            <label>
              Working days
              <input
                name="duration"
                type="number"
                min={1}
                max={3660}
                step={1}
                required
              />
            </label>
            <button disabled={pending}>Calculate dates</button>
          </form>
          {calculation && (
            <div role="status">
              <p>
                Calendar version {calculation.versionNumber}. Requested start:{" "}
                {calculation.requestedStart}. Effective start:{" "}
                {calculation.effectiveStart}
                {calculation.adjusted ? " (moved to the next working day)" : ""}
                .
              </p>
              <p>
                Due: {calculation.dueLocal} ({calculation.timezone}). UTC:{" "}
                {calculation.dueAt}.
              </p>
              <p>
                Counted dates: {calculation.countedDates.join(", ")}. Next
                working-day handoff: {calculation.nextHandoff} UTC.
              </p>
            </div>
          )}
        </section>
      )}
    </>
  );
}
