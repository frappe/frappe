import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getSession, getTranslations, logout } from "../index";

const fetchMock = vi.fn<typeof fetch>();

function respond(body: unknown, status = 200) {
  fetchMock.mockImplementation(async () => new Response(JSON.stringify(body), { status }));
}

function lastCall(): { url: string; method?: string; body?: unknown } {
  const [url, init] = fetchMock.mock.calls.at(-1)!;
  return {
    url: String(url),
    method: init?.method,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : init?.body,
  };
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

describe("getSession", () => {
  it("reads the session route and returns the body under data", async () => {
    respond({
      data: {
        user: {
          name: "alice@example.com",
          full_name: "Alice",
          email: "alice@example.com",
          user_image: null,
        },
        roles: ["System Manager", "All"],
        lang: "en",
        timezone: "Asia/Kolkata",
        defaults: { company: "Example Ltd" },
      },
    });
    const { data } = await getSession();
    expect(lastCall()).toMatchObject({ url: "/api/v2/session", method: "GET" });
    expect(data.user.full_name).toBe("Alice");
    expect(data.roles).toEqual(["System Manager", "All"]);
    expect(data.defaults).toEqual({ company: "Example Ltd" });
  });

  it("returns the Guest session rather than an error", async () => {
    respond({
      data: {
        user: { name: "Guest", full_name: "Guest", email: "", user_image: null },
        roles: ["Guest"],
        lang: "en",
        timezone: "Asia/Kolkata",
        defaults: {},
      },
    });
    const { data } = await getSession();
    expect(data.user.name).toBe("Guest");
  });
});

describe("logout", () => {
  it("posts to the logout method", async () => {
    respond({ message: "Logged out" });
    await logout();
    expect(lastCall()).toMatchObject({ url: "/api/v2/method/logout", method: "POST" });
  });
});

describe("getTranslations", () => {
  it("asks for one language at one version, on a cacheable GET", async () => {
    respond({ data: { Save: "Speichern" } });
    const { data } = await getTranslations("de", "v-7");
    expect(lastCall()).toMatchObject({
      url: "/api/v2/method/frappe.translate.get_boot_translations?lang=de&v=v-7",
      method: "GET",
    });
    expect(data).toEqual({ Save: "Speichern" });
  });
});
