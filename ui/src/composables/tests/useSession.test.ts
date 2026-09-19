// The session store: a published session is read as it is, and everyone else shares one fetch.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp } from "vue";
import type { Session } from "../../api";
import { currentSession, provideSession, resetSession, setSession, useSession } from "../useSession";

const api = vi.hoisted(() => ({ getSession: vi.fn() }));

vi.mock("../../api", () => ({ getSession: api.getSession }));

function aSession(email = "alice@example.com"): Session {
  return {
    user: { name: email, full_name: "Alice", email, user_image: null },
    roles: ["System Manager", "All"],
    lang: "en",
    timezone: "Asia/Kolkata",
    defaults: { company: "Example Ltd" },
  };
}

// `inject` only resolves an app-level provide inside a running app context.
function host() {
  return createApp({ render: () => null });
}

beforeEach(() => {
  api.getSession.mockReset();
  resetSession();
});

describe("useSession", () => {
  it("reads a provided session without fetching", () => {
    const app = host();
    const published = aSession();
    provideSession(app, published);

    const { session, loading, error } = app.runWithContext(() => useSession());
    expect(session.value).toBe(published);
    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(api.getSession).not.toHaveBeenCalled();
  });

  it("fetches once for two callers when nothing was provided", async () => {
    api.getSession.mockResolvedValue({ data: aSession() });
    const app = host();

    const first = app.runWithContext(() => useSession());
    const second = app.runWithContext(() => useSession());
    expect(first.loading.value).toBe(true);

    await vi.waitFor(() => expect(first.session.value).not.toBeNull());
    expect(api.getSession).toHaveBeenCalledTimes(1);
    expect(second.session.value).toBe(first.session.value);
    expect(first.loading.value).toBe(false);
  });

  it("keeps the failure and stops loading when the fetch fails", async () => {
    const failure = new Error("no session");
    api.getSession.mockRejectedValue(failure);
    const app = host();

    const { session, loading, error } = app.runWithContext(() => useSession());
    await vi.waitFor(() => expect(error.value).toBe(failure));
    expect(session.value).toBeNull();
    expect(loading.value).toBe(false);
  });

  it("re-reads on reload", async () => {
    api.getSession.mockResolvedValue({ data: aSession("bob@example.com") });
    const app = host();
    setSession(aSession());

    const { session, reload } = app.runWithContext(() => useSession());
    await reload();
    expect(session.value?.user.email).toBe("bob@example.com");
    expect(api.getSession).toHaveBeenCalledTimes(1);
  });
});

describe("currentSession", () => {
  it("returns the object the host published", () => {
    const published = aSession();
    setSession(published);
    expect(currentSession()).toBe(published);
  });

  it("returns what the fetch landed, for a caller that cannot inject", async () => {
    api.getSession.mockResolvedValue({ data: aSession() });
    const app = host();

    const { session } = app.runWithContext(() => useSession());
    await vi.waitFor(() => expect(session.value).not.toBeNull());
    expect(currentSession()).toBe(session.value);
  });
});

describe("resetSession", () => {
  it("clears the session and lets the next caller fetch again", async () => {
    api.getSession.mockResolvedValue({ data: aSession() });
    setSession(aSession("carol@example.com"));

    resetSession();
    expect(currentSession()).toBeNull();

    const app = host();
    const { session } = app.runWithContext(() => useSession());
    await vi.waitFor(() => expect(session.value).not.toBeNull());
    expect(api.getSession).toHaveBeenCalledTimes(1);
    expect(currentSession()?.user.email).toBe("alice@example.com");
  });
});
