// A second page made with the builder: one list, one event and one extra member.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { watchEffect } from "vue";

vi.mock("frappe-ui", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  dialog: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({ runMethod: vi.fn() }));

import { createPageEngine } from "../createPageEngine";
import { FIRST_PAINT_LIMIT_MS } from "../paintGate";
import { Surface } from "../surface";
import type { Handler, Registration } from "../types";

let sources: Registration[];

function makeEngine(sourcesReady?: () => Promise<void>) {
  const widgets = new Surface({ surface: "widgets", keys: ["name", "label"] });
  widgets.provideBuiltins(() => [{ name: "a" }, { name: "b" }]);
  return createPageEngine({
    doctype: "Widget Board",
    name: "board",
    lists: { widgets },
    events: ["onPing"],
    sources: () => sources,
    extras: () => ({
      get count() {
        return widgets.visible().length;
      },
    }),
    meta: () => null,
    perms: () => ({}),
    roles: () => [],
    router: {} as any,
    sourcesReady,
  });
}

type Board = ReturnType<typeof makeEngine>["page"];

function register(source: string, handlers: Record<string, (page: Board) => unknown>) {
  sources.push({ source, handlers: handlers as Record<string, Handler> });
}

function gate() {
  let open!: () => void;
  const opened = new Promise<void>((resolve) => (open = resolve));
  return { opened, open };
}

const drawn = (engine: ReturnType<typeof makeEngine>) =>
  engine.lists.widgets.visible().map((one) => one.name);

beforeEach(() => {
  sources = [];
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("a page made with the builder", () => {
  it("folds a source's ops over a fresh copy of the built-ins on every replay", async () => {
    register("one", {
      onRefresh: (page) => {
        page.widgets.hide("a");
        page.widgets.add({ name: "c" }, { before: "b" });
      },
    });
    const engine = makeEngine();

    await engine.refresh();
    expect(drawn(engine)).toEqual(["c", "b"]);
    await engine.refresh();
    expect(drawn(engine)).toEqual(["c", "b"]);
    expect(engine.page.count).toBe(2);
  });

  it("commits once per handler, when it ends", async () => {
    const pause = gate();
    register("one", {
      onPing: async (page) => {
        page.widgets.add({ name: "c" });
        await pause.opened;
        page.widgets.hide("a");
      },
    });
    const engine = makeEngine();
    await engine.refresh();
    let paints = -1;
    watchEffect(
      () => {
        engine.lists.widgets.resolve();
        paints += 1;
      },
      { flush: "sync" },
    );

    const firing = engine.fire("onPing");
    await Promise.resolve();
    expect(drawn(engine)).toEqual(["a", "b"]);
    pause.open();
    await firing;

    expect(drawn(engine)).toEqual(["b", "c"]);
    expect(paints).toBe(1);
  });

  it("holds its first paint until the sources are ready", async () => {
    const ready = gate();
    register("one", { onRefresh: (page) => page.widgets.add({ name: "c" }) });
    const engine = makeEngine(() => ready.opened);

    const refreshing = engine.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS - 1);
    expect(engine.ready.value).toBe(false);
    expect(drawn(engine)).toEqual(["a", "b"]);

    ready.open();
    await refreshing;
    expect(engine.ready.value).toBe(true);
    expect(drawn(engine)).toEqual(["a", "b", "c"]);
  });

  it("paints without a slow source after the limit, and draws it when it finishes", async () => {
    const pause = gate();
    register("slow", {
      onRefresh: async (page) => {
        await pause.opened;
        page.widgets.add({ name: "slow" });
      },
    });
    register("fast", { onRefresh: (page) => page.widgets.add({ name: "fast" }) });
    const engine = makeEngine();

    void engine.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS - 1);
    expect(engine.ready.value).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(engine.ready.value).toBe(true);
    expect(drawn(engine)).toEqual(["a", "b", "fast"]);

    pause.open();
    await vi.advanceTimersByTimeAsync(0);
    expect(drawn(engine)).toEqual(["a", "b", "fast", "slow"]);
  });
});
