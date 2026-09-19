// Boot's one side effect: the CSRF token lands where frappe-ui's request layer reads it.
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@framework/ui/api";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));

vi.mock("@framework/ui/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@framework/ui/api")>()),
  runMethod: fake.runMethod,
}));

import { BootUnauthorized, fetchBoot } from "@/boot";

function refuse(status: number) {
  fake.runMethod.mockRejectedValue(new ApiError({ type: "PermissionError" }, status));
}

describe("fetchBoot", () => {
  afterEach(() => {
    fake.runMethod.mockReset();
    delete (window as { csrf_token?: string }).csrf_token;
  });

  it("publishes the session's CSRF token on window for frappe-ui's requests", async () => {
    fake.runMethod.mockResolvedValue({ data: { csrf_token: "tok-123", app_order: ["frappe"] } });

    const boot = await fetchBoot();

    expect(boot.csrf_token).toBe("tok-123");
    expect(window.csrf_token).toBe("tok-123");
    expect(fake.runMethod).toHaveBeenCalledWith(
      "frappe.shell.boot.get_boot",
      { path: location.pathname },
      { http: "GET" }
    );
  });

  it("leaves no token behind when boot is refused", async () => {
    refuse(403);
    await expect(fetchBoot()).rejects.toBeInstanceOf(BootUnauthorized);
    expect(window.csrf_token).toBeUndefined();
  });

  it("sends an expired session to login too", async () => {
    refuse(401);
    await expect(fetchBoot()).rejects.toBeInstanceOf(BootUnauthorized);
  });

  it("keeps any other refusal a plain error carrying the status", async () => {
    refuse(500);
    await expect(fetchBoot()).rejects.toThrow("Boot failed with 500");
    await expect(fetchBoot()).rejects.not.toBeInstanceOf(BootUnauthorized);
  });

  it("keeps the server's own error as the cause", async () => {
    refuse(500);
    const failure = await fetchBoot().catch((e: Error) => e);
    expect((failure as Error).cause).toBeInstanceOf(ApiError);
    expect(((failure as Error).cause as ApiError).status).toBe(500);
  });
});
