import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiUrl, request, requestHeaders } from "../request";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiUrl", () => {
  it("prefixes /api/v2 and drops null and undefined query values", () => {
    expect(apiUrl("/document/ToDo", { limit: 20, start: undefined, fields: null })).toBe(
      "/api/v2/document/ToDo?limit=20"
    );
    expect(apiUrl("/method/ping")).toBe("/api/v2/method/ping");
  });

  it("JSON-encodes arrays and objects, and leaves strings as they are", () => {
    const url = apiUrl("/document/ToDo", {
      fields: ["name", "status"],
      filters: { status: ["=", "Open"] },
      or_filters: [["priority", "=", "High"]],
      order_by: "modified desc",
      as_dict: false,
      debug: true,
    });
    const query = new URL(url, "http://x").searchParams;
    expect(query.get("fields")).toBe('["name","status"]');
    expect(query.get("filters")).toBe('{"status":["=","Open"]}');
    expect(query.get("or_filters")).toBe('[["priority","=","High"]]');
    expect(query.get("order_by")).toBe("modified desc");
    expect(query.get("as_dict")).toBe("0");
    expect(query.get("debug")).toBe("1");
  });
});

describe("requestHeaders", () => {
  afterEach(() => {
    delete (globalThis as { csrf_token?: string }).csrf_token;
  });

  it("sends the CSRF token the host page exposes, and skips the unrendered placeholder", () => {
    (globalThis as { csrf_token?: string }).csrf_token = "tok-1";
    expect(requestHeaders()["X-Frappe-CSRF-Token"]).toBe("tok-1");
    (globalThis as { csrf_token?: string }).csrf_token = "{{ csrf_token }}";
    expect(requestHeaders()["X-Frappe-CSRF-Token"]).toBeUndefined();
  });

  it("names the site, and sets a JSON content type only for a JSON body", () => {
    expect(requestHeaders()["X-Frappe-Site-Name"]).toBe(globalThis.location.hostname);
    expect(requestHeaders()["Content-Type"]).toContain("application/json");
    expect(requestHeaders({ json: false })["Content-Type"]).toBeUndefined();
  });
});

describe("request", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("sends a JSON body with the method given and returns the envelope", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ data: { name: "T-1" } }));
    const envelope = await request("PATCH", "/document/ToDo/T-1", { body: { name: "T-1" } });
    expect(envelope.data).toEqual({ name: "T-1" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v2/document/ToDo/T-1");
    expect(init?.method).toBe("PATCH");
    expect(init?.body).toBe('{"name":"T-1"}');
    expect((init?.headers as Record<string, string>)["Content-Type"]).toContain("json");
  });

  it("sends no body and no content type on a GET", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ data: [] }));
    await request("GET", "/document/ToDo", { query: { limit: 1 } });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v2/document/ToDo?limit=1");
    expect(init?.body).toBeUndefined();
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("rejects with the server's first error", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ errors: [{ type: "PermissionError", message: "Not permitted" }] }, 403)
    );
    await expect(request("GET", "/document/ToDo/T-1")).rejects.toMatchObject({
      name: "ApiError",
      type: "PermissionError",
      message: "Not permitted",
      status: 403,
    });
  });

  it("rejects a 200 with no data, naming the request, unless the route is nullable", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));
    await expect(request("GET", "/document/ToDo/T-1")).rejects.toThrow(
      expect.objectContaining({
        type: "MissingData",
        message: "GET /document/ToDo/T-1 answered 200 with no data",
      })
    );
    fetchMock.mockResolvedValue(jsonResponse({}));
    const envelope = await request("POST", "/method/logout", { nullable: true });
    expect(envelope.data).toBeNull();
  });

  it("rejects with an HTTPError when the failure body is not JSON", async () => {
    fetchMock.mockResolvedValue(new Response("<html>Bad Gateway</html>", { status: 502 }));
    await expect(request("GET", "/method/ping")).rejects.toMatchObject({
      type: "HTTPError",
      status: 502,
    });
  });

  it("maps a network failure to an ApiError and lets an abort through untouched", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(request("GET", "/method/ping")).rejects.toMatchObject({
      name: "ApiError",
      type: "NetworkError",
      status: 0,
    });
    fetchMock.mockRejectedValueOnce(new DOMException("aborted", "AbortError"));
    await expect(request("GET", "/method/ping")).rejects.toMatchObject({ name: "AbortError" });
  });

  it("passes the abort signal through", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ data: null }));
    const controller = new AbortController();
    await request("GET", "/method/ping", { signal: controller.signal });
    expect(fetchMock.mock.calls[0][1]?.signal).toBe(controller.signal);
  });
});
