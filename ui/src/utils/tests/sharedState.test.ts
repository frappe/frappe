import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { memoizedState } from "../sharedState";

describe("memoizedState.drop", () => {
  const build = vi.fn((name: string) => ({ name: ref(name) }));

  it("forgets the matching states, so the next get builds anew", () => {
    const states = memoizedState((name: string) => name, build);
    const lead = states.get("Lead");
    const deal = states.get("Deal");

    states.drop((key) => key === "Lead");

    expect(states.get("Lead")).not.toBe(lead);
    expect(states.get("Deal")).toBe(deal);
  });

  it("matches on the state as well as the key", () => {
    const states = memoizedState((name: string) => name, build);
    const lead = states.get("Lead");
    const deal = states.get("Deal");

    states.drop((_key, state) => state.name.value === "Deal");

    expect(states.get("Lead")).toBe(lead);
    expect(states.get("Deal")).not.toBe(deal);
  });

  it("leaves a dropped state working for whoever holds it", () => {
    const states = memoizedState((name: string) => name, build);
    const held = states.get("Lead");

    states.drop(() => true);
    held.name.value = "Renamed";

    expect(held.name.value).toBe("Renamed");
    expect(states.get("Lead").name.value).toBe("Lead");
  });
});
