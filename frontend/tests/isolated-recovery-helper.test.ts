import { describe, expect, it, vi } from "vitest";
import {
  IsolatedRecoveryHelper,
  type CommandExecutor,
} from "./e2e/isolated-recovery-helper";

describe("IsolatedRecoveryHelper Fail-Closed Validation", () => {
  it("rejects missing COMPOSE_PROJECT_NAME before executing any command", () => {
    const mockExecutor = vi.fn<CommandExecutor>();
    expect(
      () =>
        new IsolatedRecoveryHelper(
          {
            projectName: "",
            composeFile: "compose.test.yaml",
            envFile: "compose.test.yaml", // exists on disk
          },
          mockExecutor,
        ),
    ).toThrow(
      /Missing required isolated environment configuration 'COMPOSE_PROJECT_NAME'/,
    );
    expect(mockExecutor).not.toHaveBeenCalled();
  });

  it("rejects development project name 'enterprise-task-platform-phase2' before executing any command", () => {
    const mockExecutor = vi.fn<CommandExecutor>();
    expect(
      () =>
        new IsolatedRecoveryHelper(
          {
            projectName: "enterprise-task-platform-phase2",
            composeFile: "compose.test.yaml",
            envFile: "compose.test.yaml",
          },
          mockExecutor,
        ),
    ).toThrow(/Refusing to target development Compose project/);
    expect(mockExecutor).not.toHaveBeenCalled();
  });

  it("rejects non-existent COMPOSE_FILE before executing any command", () => {
    const mockExecutor = vi.fn<CommandExecutor>();
    expect(
      () =>
        new IsolatedRecoveryHelper(
          {
            projectName: "taskspace-rec-test1234",
            composeFile: "non-existent-file.yaml",
            envFile: "compose.test.yaml",
          },
          mockExecutor,
        ),
    ).toThrow(/Configured COMPOSE_FILE does not exist on disk/);
    expect(mockExecutor).not.toHaveBeenCalled();
  });

  it("rejects non-existent COMPOSE_ENV_FILES before executing any command", () => {
    const mockExecutor = vi.fn<CommandExecutor>();
    expect(
      () =>
        new IsolatedRecoveryHelper(
          {
            projectName: "taskspace-rec-test1234",
            composeFile: "compose.test.yaml",
            envFile: "non-existent-env-file.env",
          },
          mockExecutor,
        ),
    ).toThrow(/Configured COMPOSE_ENV_FILES does not exist on disk/);
    expect(mockExecutor).not.toHaveBeenCalled();
  });

  it("rejects development container when inspect returns 'enterprise-task-platform-phase2'", () => {
    const mockExecutor = vi.fn<CommandExecutor>((_file, args) => {
      if (args.includes("ps")) {
        return "c_dev_work_123\n";
      }
      if (
        args.includes("inspect") &&
        args.some((a) => a.includes("com.docker.compose.project"))
      ) {
        return "enterprise-task-platform-phase2|work\n";
      }
      return "";
    });

    const helper = new IsolatedRecoveryHelper(
      {
        projectName: "taskspace-rec-test1234",
        composeFile: "compose.test.yaml",
        envFile: "compose.test.yaml",
      },
      mockExecutor,
    );

    expect(() => helper.resolveContainer("work")).toThrow(
      /Safety violation: Container 'c_dev_work_123' belongs to protected development project 'enterprise-task-platform-phase2'/,
    );

    // Verify stop or pause was NEVER called
    const calledWithStopOrPause = mockExecutor.mock.calls.some(
      (call) =>
        call[1]?.includes("stop") ||
        call[0] === "pause" ||
        call[1]?.includes("pause"),
    );
    expect(calledWithStopOrPause).toBe(false);
  });

  it("rejects container when project ownership mismatches expected isolated project", () => {
    const mockExecutor = vi.fn<CommandExecutor>((_file, args) => {
      if (args.includes("ps")) {
        return "c_other_999\n";
      }
      if (
        args.includes("inspect") &&
        args.some((a) => a.includes("com.docker.compose.project"))
      ) {
        return "taskspace-some-other-project|job-worker\n";
      }
      return "";
    });

    const helper = new IsolatedRecoveryHelper(
      {
        projectName: "taskspace-rec-target-project",
        composeFile: "compose.test.yaml",
        envFile: "compose.test.yaml",
      },
      mockExecutor,
    );

    expect(() => helper.resolveContainer("job-worker")).toThrow(
      /Ownership mismatch: Container 'c_other_999' belongs to project 'taskspace-some-other-project', expected isolated project 'taskspace-rec-target-project'/,
    );
  });

  it("rejects container when service label mismatches requested target", () => {
    const mockExecutor = vi.fn<CommandExecutor>((_file, args) => {
      if (args.includes("ps")) {
        return "c_wrong_service_1\n";
      }
      if (
        args.includes("inspect") &&
        args.some((a) => a.includes("com.docker.compose.project"))
      ) {
        return "taskspace-rec-target-project|notification\n";
      }
      return "";
    });

    const helper = new IsolatedRecoveryHelper(
      {
        projectName: "taskspace-rec-target-project",
        composeFile: "compose.test.yaml",
        envFile: "compose.test.yaml",
      },
      mockExecutor,
    );

    expect(() => helper.resolveContainer("job-worker")).toThrow(
      /Service mismatch: Container 'c_wrong_service_1' has service label 'notification', expected 'job-worker'/,
    );
  });

  it("fails closed on ambiguous service resolution when multiple container IDs are returned", () => {
    const mockExecutor = vi.fn<CommandExecutor>((_file, args) => {
      if (args.includes("ps")) {
        return "c_dup_1\nc_dup_2\n";
      }
      return "";
    });

    const helper = new IsolatedRecoveryHelper(
      {
        projectName: "taskspace-rec-target-project",
        composeFile: "compose.test.yaml",
        envFile: "compose.test.yaml",
      },
      mockExecutor,
    );

    expect(() => helper.resolveContainer("gateway")).toThrow(
      /Ambiguous target: Service 'gateway' resolved to multiple containers \(c_dup_1, c_dup_2\)/,
    );
  });

  it("executes lifecycle operations when ownership and config are verified", () => {
    let currentStatus = "running";
    const executedCommands: string[][] = [];
    const mockExecutor = vi.fn<CommandExecutor>((file, args) => {
      executedCommands.push([file, ...args]);
      if (args.includes("stop")) currentStatus = "exited";
      if (args[0] === "pause") currentStatus = "paused";
      if (args[0] === "unpause" || args.includes("start"))
        currentStatus = "running";

      if (args.includes("ps") && args.includes("-q")) {
        return "c_valid_123\n";
      }
      if (
        args.includes("inspect") &&
        args.some((a) => a.includes("com.docker.compose.project"))
      ) {
        return "taskspace-rec-verified|work\n";
      }
      if (args.includes("inspect") && args.includes("{{.Name}}")) {
        return "/taskspace-rec-verified-work-1\n";
      }
      if (args.includes("inspect") && args.includes("{{.State.Status}}")) {
        return `${currentStatus}\n`;
      }
      return "";
    });

    const helper = new IsolatedRecoveryHelper(
      {
        projectName: "taskspace-rec-verified",
        composeFile: "compose.test.yaml",
        envFile: "compose.test.yaml",
      },
      mockExecutor,
    );

    helper.stopService("work");
    expect(
      executedCommands.some(
        (cmd) =>
          cmd[0] === "docker" &&
          cmd.includes("compose") &&
          cmd.includes("-p") &&
          cmd.includes("taskspace-rec-verified") &&
          cmd.includes("stop") &&
          cmd.includes("work"),
      ),
    ).toBe(true);

    helper.pauseService("work");
    expect(
      executedCommands.some(
        (cmd) =>
          cmd[0] === "docker" && cmd[1] === "pause" && cmd[2] === "c_valid_123",
      ),
    ).toBe(true);

    helper.unpauseService("work");
    expect(
      executedCommands.some(
        (cmd) =>
          cmd[0] === "docker" &&
          cmd[1] === "unpause" &&
          cmd[2] === "c_valid_123",
      ),
    ).toBe(true);

    currentStatus = "running";
    helper.startService("work");
    expect(
      executedCommands.some(
        (cmd) =>
          cmd[0] === "docker" && cmd[1] === "start" && cmd[2] === "c_valid_123",
      ),
    ).toBe(true);
  });
});
