// Boot's one side effect: the CSRF token lands where frappe-ui's request layer reads it.
import { afterEach, describe, expect, it, vi } from "vitest";

import { BootUnauthorized, fetchBoot } from "@/boot";

function respond(status: number, message?: object) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: status < 400,
      status,
      json: async () => ({ message }),
    }))
  );
}

describe("fetchBoot", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete (window as { csrf_token?: string }).csrf_token;
  });

  it("publishes the session's CSRF token on window for frappe-ui's requests", async () => {
    respond(200, { csrf_token: "tok-123", app_order: ["frappe"] });
    const boot = await fetchBoot();
    expect(boot.csrf_token).toBe("tok-123");
    expect(window.csrf_token).toBe("tok-123");
  });

  it("leaves no token behind when boot is refused", async () => {
    respond(403);
    await expect(fetchBoot()).rejects.toBeInstanceOf(BootUnauthorized);
    expect(window.csrf_token).toBeUndefined();
  });
});
