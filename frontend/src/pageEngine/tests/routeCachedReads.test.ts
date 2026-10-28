// The default `page.cached`: one fetch per key on a route path, dropped on another path or on leave.
import { describe, expect, it, vi } from "vitest";
import { RouteCachedReads } from "../routeCachedReads";

function makeReads(path = "/board") {
  const router = { currentRoute: { value: { path } } };
  const reads = new RouteCachedReads(router as any, "[board page]");
  const landed = async () => {
    await Promise.all(reads.fetchUnfetched().map((late) => late.settled));
  };
  return { reads, router, landed };
}

describe("RouteCachedReads", () => {
  it("fetches a key once on a path and answers its value after it lands", async () => {
    const { reads, landed } = makeReads();
    const fetch = vi.fn(() => 7);

    expect(reads.read("acme", "count", fetch)).toBeUndefined();
    await landed();
    await landed();

    expect(reads.read("acme", "count", fetch)).toBe(7);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("keeps one value per source on the same key", async () => {
    const { reads, landed } = makeReads();
    reads.read("acme", "count", () => 1);
    reads.read("client-script:x", "count", () => 2);
    await landed();

    expect(reads.read("acme", "count", () => 0)).toBe(1);
    expect(reads.read("client-script:x", "count", () => 0)).toBe(2);
  });

  it("drops its values when the route moves to another path", async () => {
    const { reads, router, landed } = makeReads();
    reads.read("acme", "count", () => 1);
    await landed();

    router.currentRoute.value.path = "/board/other";
    expect(reads.read("acme", "count", () => 2)).toBeUndefined();
    await landed();
    expect(reads.read("acme", "count", () => 3)).toBe(2);
  });

  it("drops a fetch that lands after the route moved on", async () => {
    const { reads, router } = makeReads();
    let answer!: (value: number) => void;
    reads.read("acme", "count", () => new Promise<number>((resolve) => (answer = resolve)));
    const [late] = reads.fetchUnfetched();

    router.currentRoute.value.path = "/board/other";
    expect(reads.read("acme", "count", () => 2)).toBeUndefined();
    answer(1);
    await late.settled;

    expect(reads.read("acme", "count", () => 2)).toBeUndefined();
  });

  it("holds nothing after clear, so a return visit fetches again", async () => {
    const { reads, landed } = makeReads();
    const fetch = vi.fn(() => 1);
    reads.read("acme", "count", fetch);
    await landed();

    reads.clear();
    expect(reads.read("acme", "count", fetch)).toBeUndefined();
    await landed();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("answers no value when a fetch fails, with a warning", async () => {
    const { reads, landed } = makeReads();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    reads.read("acme", "count", () => Promise.reject(new Error("down")));
    await landed();

    expect(reads.read("acme", "count", () => 0)).toBeUndefined();
    expect(warn.mock.calls[0][0]).toContain('[board page] acme page.cached("count") failed');
    warn.mockRestore();
  });
});
