import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { holdFresh, landFresh, memoizedState } from "../sharedState";

describe("memoizedState.stale", () => {
  const build = vi.fn((name: string) => ({ name: ref(name) }));

  it("sets the matching states aside, so the next get builds anew", () => {
    const states = memoizedState((name: string) => name, build);
    const lead = states.get("Lead");
    const deal = states.get("Deal");

    states.stale((key) => key === "Lead");

    expect(states.get("Lead")).not.toBe(lead);
    expect(states.get("Deal")).toBe(deal);
  });

  it("matches on the state as well as the key", () => {
    const states = memoizedState((name: string) => name, build);
    const lead = states.get("Lead");
    const deal = states.get("Deal");

    states.stale((_key, state) => state.name.value === "Deal");

    expect(states.get("Lead")).toBe(lead);
    expect(states.get("Deal")).not.toBe(deal);
  });

  it("leaves a stale state working for whoever holds it", () => {
    const states = memoizedState((name: string) => name, build);
    const held = states.get("Lead");

    states.stale(() => true);
    held.name.value = "Renamed";

    expect(held.name.value).toBe("Renamed");
    expect(states.get("Lead").name.value).toBe("Lead");
  });

  it("hands the stale state to the next build of its key, once", () => {
    const seeded = vi.fn((name: string, stale?: { name: string }) => ({
      name,
      from: stale,
    }));
    const states = memoizedState((name: string) => name, seeded);
    const old = states.get("Lead");

    states.stale(() => true);
    const fresh = states.get("Lead");
    states.stale(() => true);
    states.get("Lead");

    expect(seeded).toHaveBeenNthCalledWith(1, "Lead", undefined);
    expect(seeded).toHaveBeenNthCalledWith(2, "Lead", old);
    expect(seeded).toHaveBeenNthCalledWith(3, "Lead", fresh);
  });

  it("builds without a stale state for a key that was never set aside", () => {
    const seeded = vi.fn((name: string, stale?: object) => ({ name, from: stale }));
    const states = memoizedState((name: string) => name, seeded);
    states.get("Lead");

    states.stale((key) => key === "Lead");
    states.get("Deal");

    expect(seeded).toHaveBeenLastCalledWith("Deal", undefined);
  });

  it("forgets stale states on reset", () => {
    const seeded = vi.fn((name: string, stale?: object) => ({ name, from: stale }));
    const states = memoizedState((name: string) => name, seeded);
    states.get("Lead");

    states.stale(() => true);
    states.reset();
    states.get("Lead");

    expect(seeded).toHaveBeenLastCalledWith("Lead", undefined);
  });
});

describe("landFresh", () => {
  it("runs the commit at once when no hold is open", () => {
    const commit = vi.fn();

    landFresh(commit);

    expect(commit).toHaveBeenCalledOnce();
  });

  it("waits for the last of two holds to be released", () => {
    const commit = vi.fn();
    const releaseFirst = holdFresh();
    const releaseSecond = holdFresh();

    landFresh(commit);
    releaseFirst();
    expect(commit).not.toHaveBeenCalled();

    releaseSecond();
    expect(commit).toHaveBeenCalledOnce();
  });

  it("runs the held commits in the order they landed", () => {
    const order: string[] = [];
    const release = holdFresh();

    landFresh(() => order.push("meta"));
    landFresh(() => order.push("rows"));
    release();

    expect(order).toEqual(["meta", "rows"]);
  });

  it("ignores a second release of the same hold", () => {
    const commit = vi.fn();
    const releaseFirst = holdFresh();
    const releaseSecond = holdFresh();

    landFresh(commit);
    releaseFirst();
    releaseFirst();
    expect(commit).not.toHaveBeenCalled();

    releaseSecond();
    releaseSecond();
    expect(commit).toHaveBeenCalledOnce();
  });

  it("runs a commit at once again after the holds are released", () => {
    holdFresh()();
    const commit = vi.fn();

    landFresh(commit);

    expect(commit).toHaveBeenCalledOnce();
  });
});
