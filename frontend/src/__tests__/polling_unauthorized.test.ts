import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchJobStats, fetchJobs, ApiError, UNAUTHORIZED_EVENT } from "../lib/api";

describe("401 Unauthorized Polling Termination", () => {
  let mockLocation: { href: string };
  let eventListeners: Record<string, ((event: unknown) => void)[]> = {};

  beforeEach(() => {
    vi.clearAllMocks();
    mockLocation = { href: "http://localhost:3000" };
    eventListeners = {};

    // Mock browser window environment
    (global as unknown as { window: unknown }).window = {
      location: mockLocation,
      dispatchEvent: vi.fn((event: { type: string }) => {
        const listeners = eventListeners[event.type] || [];
        listeners.forEach((listener) => listener(event));
        return true;
      }),
      addEventListener: vi.fn((event: string, listener: (event: unknown) => void) => {
        if (!eventListeners[event]) eventListeners[event] = [];
        eventListeners[event].push(listener);
      }),
      removeEventListener: vi.fn((event: string, listener: (event: unknown) => void) => {
        if (eventListeners[event]) {
          eventListeners[event] = eventListeners[event].filter((l) => l !== listener);
        }
      }),
    };

    (global as unknown as { CustomEvent: unknown }).CustomEvent = class CustomEvent {
      type: string;
      constructor(type: string) {
        this.type = type;
      }
    };
  });

  afterEach(() => {
    delete (global as unknown as { window?: unknown }).window;
    delete (global as unknown as { CustomEvent?: unknown }).CustomEvent;
  });

  it("dispatches UNAUTHORIZED_EVENT and redirects to /login on 401 response from fetchJobStats", async () => {
    const eventSpy = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, eventSpy);

    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 401,
      text: async () => "Unauthorized session expired",
    } as Response);

    await expect(fetchJobStats()).rejects.toThrow(ApiError);

    expect(eventSpy).toHaveBeenCalledTimes(1);
    expect(window.location.href).toBe("/login");
  });

  it("dispatches UNAUTHORIZED_EVENT and redirects to /login on 401 response from fetchJobs", async () => {
    const eventSpy = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, eventSpy);

    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 401,
      text: async () => "Unauthorized session expired",
    } as Response);

    await expect(fetchJobs()).rejects.toThrow(ApiError);

    expect(eventSpy).toHaveBeenCalledTimes(1);
    expect(window.location.href).toBe("/login");
  });

  it("does not redirect to /login on 500 server error", async () => {
    const eventSpy = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, eventSpy);

    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: async () => "Internal Server Error",
    } as Response);

    await expect(fetchJobStats()).rejects.toThrow(ApiError);

    expect(eventSpy).not.toHaveBeenCalled();
    expect(window.location.href).not.toBe("/login");
  });
});
