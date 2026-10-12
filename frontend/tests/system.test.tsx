import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SystemPanel } from "@/features/system/system-panel";
import { ConnectionStatus } from "@/features/system/connection-status";
const data = {
  systemInfo: {
    name: "Enterprise Task Platform Gateway",
    version: "0.1.0",
    environment: "test",
    status: "AVAILABLE",
  },
};
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <ConnectionStatus />
      <SystemPanel />
    </QueryClientProvider>,
  );
  return client;
}
afterEach(() => vi.unstubAllGlobals());
describe("live gateway status", () => {
  it("shows a loading state before a response", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {})),
    );
    mount();
    expect(screen.getByLabelText("Connecting to gateway")).toBeInTheDocument();
  });
  it("displays actual gateway data", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ data }) });
    vi.stubGlobal("fetch", fetch);
    mount();
    expect(await screen.findByText("Gateway is reachable")).toBeInTheDocument();
    expect(screen.getByText("test")).toBeInTheDocument();
    expect(fetch.mock.calls[0][0]).toBe("/graphql");
    expect(JSON.parse(fetch.mock.calls[0][1].body).operationName).toBe(
      "SystemInfo",
    );
  });
  it("marks stale data unavailable after failure and recovers on retry", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ data }) })
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue({ ok: true, json: async () => ({ data }) });
    vi.stubGlobal("fetch", fetch);
    mount();
    await screen.findByText("Gateway is reachable");
    fireEvent.click(screen.getByRole("button", { name: "Refresh status" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Gateway unavailable",
    );
    expect(screen.queryByText("Gateway is reachable")).not.toBeInTheDocument();
    expect(screen.queryByText("Gateway connected")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(screen.getByText("Gateway is reachable")).toBeInTheDocument(),
    );
  });
  it("treats GraphQL errors in HTTP 200 as failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ errors: [{ message: "error" }] }),
      }),
    );
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Gateway unavailable",
    );
  });
});
