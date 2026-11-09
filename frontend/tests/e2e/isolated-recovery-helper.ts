import { execFileSync, type IOType } from "node:child_process";
import { existsSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

export interface IsolatedRunConfig {
  projectName: string;
  composeFile: string;
  envFile: string;
  baseUrl: string;
  gatewayUrl: string;
  keycloakUrl: string;
}

export type CommandExecutor = (
  file: string,
  args: string[],
  options?: {
    encoding?: BufferEncoding;
    stdio?: IOType | Array<IOType | "ipc" | number | null | undefined>;
    env?: NodeJS.ProcessEnv;
  },
) => string;

const DEFAULT_DEV_PROJECT = "enterprise-task-platform-phase2";
const SERVICE_NAME_PATTERN = /^[a-z][a-z0-9_-]{0,63}$/;

function findRepoRoot(): string {
  if (
    typeof import.meta !== "undefined" &&
    typeof import.meta.url === "string" &&
    import.meta.url.startsWith("file:")
  ) {
    try {
      const candidate = fileURLToPath(new URL("../../..", import.meta.url));
      if (existsSync(resolve(candidate, "compose.yaml"))) return candidate;
    } catch {
      // Fall through
    }
  }
  const cwd = process.cwd();
  if (existsSync(resolve(cwd, "compose.yaml"))) return cwd;
  if (existsSync(resolve(cwd, "../compose.yaml"))) return resolve(cwd, "..");
  return cwd;
}

const REPO_ROOT = findRepoRoot();

function resolveFile(filePath: string): string {
  if (isAbsolute(filePath)) return filePath;
  const fromRepo = resolve(REPO_ROOT, filePath);
  if (existsSync(fromRepo)) return fromRepo;
  const fromCwd = resolve(process.cwd(), filePath);
  if (existsSync(fromCwd)) return fromCwd;
  return fromRepo;
}

export function defaultExecutor(
  file: string,
  args: string[],
  options: {
    encoding?: BufferEncoding;
    stdio?: IOType | Array<IOType | "ipc" | number | null | undefined>;
    env?: NodeJS.ProcessEnv;
  } = {},
): string {
  return execFileSync(file, args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    ...options,
  });
}

export class IsolatedRecoveryHelper {
  private readonly config: IsolatedRunConfig;
  private readonly executor: CommandExecutor;

  constructor(
    customConfig?: Partial<IsolatedRunConfig>,
    executor: CommandExecutor = defaultExecutor,
  ) {
    this.executor = executor;
    this.config = this.validateConfig(customConfig);
  }

  private validateConfig(
    custom?: Partial<IsolatedRunConfig>,
  ): IsolatedRunConfig {
    const projectName =
      custom?.projectName ?? process.env.COMPOSE_PROJECT_NAME ?? "";
    if (!projectName || !projectName.trim()) {
      throw new Error(
        "Fail-closed: Missing required isolated environment configuration 'COMPOSE_PROJECT_NAME'. Refusing to execute unscoped recovery operations.",
      );
    }
    if (
      projectName.trim() === DEFAULT_DEV_PROJECT ||
      projectName.trim().includes("phase2")
    ) {
      throw new Error(
        `Refusing to target development Compose project '${projectName}'. Recovery operations require a dedicated isolated test project.`,
      );
    }

    const rawComposeFile =
      custom?.composeFile ?? process.env.COMPOSE_FILE ?? "";
    if (!rawComposeFile || !rawComposeFile.trim()) {
      throw new Error(
        "Fail-closed: Missing required isolated environment configuration 'COMPOSE_FILE'.",
      );
    }
    const composeFile = resolveFile(rawComposeFile.trim());
    if (!existsSync(composeFile)) {
      throw new Error(
        `Fail-closed: Configured COMPOSE_FILE does not exist on disk: '${rawComposeFile}'.`,
      );
    }

    const rawEnvFile = custom?.envFile ?? process.env.COMPOSE_ENV_FILES ?? "";
    if (!rawEnvFile || !rawEnvFile.trim()) {
      throw new Error(
        "Fail-closed: Missing required isolated environment configuration 'COMPOSE_ENV_FILES'.",
      );
    }
    const envFile = resolveFile(rawEnvFile.trim());
    if (!existsSync(envFile)) {
      throw new Error(
        `Fail-closed: Configured COMPOSE_ENV_FILES does not exist on disk: '${rawEnvFile}'.`,
      );
    }

    const baseUrl =
      custom?.baseUrl ??
      process.env.PLAYWRIGHT_BASE_URL ??
      "http://localhost:3110";
    const gatewayUrl =
      custom?.gatewayUrl ?? process.env.GATEWAY_URL ?? "http://localhost:8110";
    const keycloakUrl =
      custom?.keycloakUrl ??
      process.env.KEYCLOAK_URL ??
      "http://localhost:8180";

    return {
      projectName: projectName.trim(),
      composeFile,
      envFile,
      baseUrl,
      gatewayUrl,
      keycloakUrl,
    };
  }

  public getConfig(): Readonly<IsolatedRunConfig> {
    return this.config;
  }

  public getBaseUrl(): string {
    return this.config.baseUrl;
  }

  public getGatewayUrl(): string {
    return this.config.gatewayUrl;
  }

  public getKeycloakUrl(): string {
    return this.config.keycloakUrl;
  }

  public getRepoRoot(): string {
    return REPO_ROOT;
  }

  public buildComposeArgs(
    subCommand: string,
    ...extraArgs: string[]
  ): string[] {
    return [
      "compose",
      "-p",
      this.config.projectName,
      "-f",
      this.config.composeFile,
      "--env-file",
      this.config.envFile,
      subCommand,
      ...extraArgs,
    ];
  }

  public resolveContainer(service: string): { id: string; name: string } {
    if (!SERVICE_NAME_PATTERN.test(service)) {
      throw new Error(`Invalid service name: '${service}'.`);
    }

    const psArgs = this.buildComposeArgs("ps", "-a", "-q", service);
    const rawIds = this.executor("docker", psArgs).trim();
    if (!rawIds) {
      throw new Error(
        `Service '${service}' has no container in isolated project '${this.config.projectName}'.`,
      );
    }
    const containerIds = rawIds
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (containerIds.length > 1) {
      throw new Error(
        `Ambiguous target: Service '${service}' resolved to multiple containers (${containerIds.join(", ")}) in project '${this.config.projectName}'. Stopping execution.`,
      );
    }
    const containerId = containerIds[0];

    // Positive ownership inspection: Project AND Service labels
    const inspectLabelsArgs = [
      "inspect",
      "--format",
      '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}',
      containerId,
    ];
    const labelsRaw = this.executor("docker", inspectLabelsArgs).trim();
    const [projectLabel, serviceLabel] = labelsRaw.split("|");

    if (
      projectLabel === DEFAULT_DEV_PROJECT ||
      projectLabel?.includes("phase2")
    ) {
      throw new Error(
        `Safety violation: Container '${containerId}' belongs to protected development project '${DEFAULT_DEV_PROJECT}'. Refusing operation.`,
      );
    }
    if (projectLabel !== this.config.projectName) {
      throw new Error(
        `Ownership mismatch: Container '${containerId}' belongs to project '${projectLabel}', expected isolated project '${this.config.projectName}'.`,
      );
    }
    if (serviceLabel !== service) {
      throw new Error(
        `Service mismatch: Container '${containerId}' has service label '${serviceLabel}', expected '${service}'.`,
      );
    }

    const inspectNameArgs = ["inspect", "--format", "{{.Name}}", containerId];
    const name = this.executor("docker", inspectNameArgs)
      .trim()
      .replace(/^\//, "");

    return { id: containerId, name };
  }

  public stopService(service: string): void {
    const container = this.resolveContainer(service);
    const stopArgs = this.buildComposeArgs("stop", service);
    this.executor("docker", stopArgs);

    // Verify container actually stopped
    const inspectStatusArgs = [
      "inspect",
      "--format",
      "{{.State.Status}}",
      container.id,
    ];
    const status = this.executor("docker", inspectStatusArgs).trim();
    if (status !== "exited") {
      throw new Error(
        `Fault verification failed: Expected service '${service}' (${container.id}) to be in 'exited' state, but found '${status}'.`,
      );
    }
  }

  public startService(service: string): void {
    const container = this.resolveContainer(service);
    this.executor("docker", ["start", container.id]);

    // Verify container is running
    const inspectStatusArgs = [
      "inspect",
      "--format",
      "{{.State.Status}}",
      container.id,
    ];
    const status = this.executor("docker", inspectStatusArgs).trim();
    if (status !== "running") {
      throw new Error(
        `Restoration verification failed: Expected service '${service}' (${container.id}) to be 'running', but found '${status}'.`,
      );
    }
  }

  public pauseService(service: string): void {
    const container = this.resolveContainer(service);
    this.executor("docker", ["pause", container.id]);

    const inspectStatusArgs = [
      "inspect",
      "--format",
      "{{.State.Status}}",
      container.id,
    ];
    const status = this.executor("docker", inspectStatusArgs).trim();
    if (status !== "paused") {
      throw new Error(
        `Fault verification failed: Expected service '${service}' (${container.id}) to be 'paused', but found '${status}'.`,
      );
    }
  }

  public unpauseService(service: string): void {
    const container = this.resolveContainer(service);
    this.executor("docker", ["unpause", container.id]);

    const inspectStatusArgs = [
      "inspect",
      "--format",
      "{{.State.Status}}",
      container.id,
    ];
    const status = this.executor("docker", inspectStatusArgs).trim();
    if (status === "paused") {
      throw new Error(
        `Restoration verification failed: Expected service '${service}' (${container.id}) to be unpaused, but it remains 'paused'.`,
      );
    }
  }

  public composeExec(service: string, commandArgs: string[]): string {
    this.resolveContainer(service);
    const execArgs = this.buildComposeArgs(
      "exec",
      "-T",
      service,
      ...commandArgs,
    );
    return this.executor("docker", execArgs);
  }

  public sql(
    service: string,
    user: string,
    database: string,
    query: string,
  ): string {
    return this.composeExec(service, [
      "psql",
      "-v",
      "ON_ERROR_STOP=1",
      "-U",
      user,
      "-d",
      database,
      "-Atc",
      query,
    ]).trim();
  }

  public async waitForHealthy(
    service: string,
    timeoutMs = 60_000,
  ): Promise<void> {
    if (!SERVICE_NAME_PATTERN.test(service)) {
      throw new Error(`Invalid service name: '${service}'.`);
    }

    const deadline = Date.now() + timeoutMs;
    const psArgs = this.buildComposeArgs("ps", "--format", "json", service);

    while (Date.now() < deadline) {
      try {
        const raw = this.executor("docker", psArgs).trim();
        if (raw) {
          const lines = raw.split(/\r?\n/).filter(Boolean);
          const parsed = JSON.parse(lines[0]);
          const state = parsed.State ?? "";
          const health = parsed.Health ?? "";
          if (state === "running" && health === "healthy") {
            return;
          }
        }
      } catch {
        // continue polling until deadline
      }
      await delay(1_000);
    }

    throw new Error(
      `Service '${service}' in project '${this.config.projectName}' did not become healthy within ${timeoutMs}ms.`,
    );
  }
}

let activeHelperInstance: IsolatedRecoveryHelper | null = null;

export function getIsolatedRecoveryHelper(): IsolatedRecoveryHelper {
  if (!activeHelperInstance) {
    activeHelperInstance = new IsolatedRecoveryHelper();
  }
  return activeHelperInstance;
}
