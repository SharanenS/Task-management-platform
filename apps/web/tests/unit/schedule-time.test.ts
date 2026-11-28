import assert from "node:assert/strict";
import { test } from "node:test";
import { scheduleTime } from "../../src/project-workspace/schedule-time.ts";

test("schedule display uses project timezone across viewer timezone differences", () => {
  const previous = process.env.TZ;
  try {
    process.env.TZ = "America/Los_Angeles";
    assert.match(
      scheduleTime("2030-01-04T11:30:00Z", "Asia/Colombo"),
      /17:00$/,
    );
    assert.match(
      scheduleTime("2030-01-04T11:30:00Z", "America/New_York"),
      /06:30$/,
    );
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});
test("schedule display preserves the project-local date across midnight", () => {
  assert.match(
    scheduleTime("2030-01-04T23:30:00Z", "Asia/Colombo"),
    /5 Jan 2030, 05:00$/,
  );
});
test("unknown schedule instants stay unknown", () => {
  assert.equal(scheduleTime(null, "Asia/Colombo"), "Unknown");
  assert.equal(scheduleTime(undefined, "Asia/Colombo"), "Unknown");
});
