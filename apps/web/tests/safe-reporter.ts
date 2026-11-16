import type {
  Reporter,
  TestCase,
  TestResult,
  FullResult,
} from "@playwright/test/reporter";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
export default class SafeReporter implements Reporter {
  results: { title: string; status: string }[] = [];
  onTestEnd(test: TestCase, result: TestResult) {
    const title = test.titlePath().filter(Boolean).join(" / ");
    this.results.push({ title, status: result.status });
    console.log(`${result.status}: ${title}`);
    if (result.status !== "passed") {
      const location = result.error?.location;
      console.log(
        location
          ? `Failure at ${location.file.split(/[\\/]/).pop()}:${location.line}`
          : "Authentication boundary failed; private diagnostics omitted.",
      );
    }
  }
  onEnd(result: FullResult) {
    const report = {
      status: result.status,
      selected: this.results.length,
      passed: this.results.filter((x) => x.status === "passed").length,
      skipped: this.results.filter((x) => x.status === "skipped").length,
      results: this.results,
    };
    const dir = resolve("test-results");
    mkdirSync(dir, { recursive: true });
    writeFileSync(
      resolve(dir, "s1-acceptance.json"),
      JSON.stringify(report, null, 2),
    );
    console.log(
      `Authentication acceptance: ${report.passed}/${report.selected} passed; ${report.skipped} skipped.`,
    );
  }
}
