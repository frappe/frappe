// What the dispatcher does with the value of a call: it checks it against the act's `input`, inline or in
// the surface's sidecar, before `run`, whoever asks.
import { beforeEach, describe, expect, it, vi } from "vitest";

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("frappe-ui", () => ({ toast }));
vi.mock("@framework/ui/api", () => ({ getTranslations: vi.fn() }));

import type { ActDispatcher, ActItem } from "../dispatcher";
import type { ActSchema } from "../schema/checkValue";

let ActInvalid: typeof import("../dispatcher").ActInvalid;
let dispatcher: ActDispatcher;
let actText: typeof import("../actText");
const run = vi.fn();

beforeEach(async () => {
  vi.resetModules();
  toast.error.mockClear();
  run.mockReset();
  actText = await import("../actText");
  const module = await import("../dispatcher");
  ActInvalid = module.ActInvalid;
  dispatcher = new module.ActDispatcher();
});

function register(surface: string, ...items: ActItem[]) {
  dispatcher.register({
    surfaces: { [surface]: () => items.map((item) => ({ item, hidden: false })) },
    context: () => ({}),
    passes: () => true,
    settled: () => undefined,
    hold: async (work) => work(),
    failed: vi.fn(),
  });
}

describe("an act with an inline input", () => {
  const input: ActSchema = { type: "object", properties: { n: { type: "integer" } }, required: ["n"] };

  it("refuses a value that does not fit, before run", async () => {
    register("page", { name: "go", input, run });

    await expect(dispatcher.run("page.go", { n: "x" })).rejects.toThrow("page.go: value.n must be an integer");
    await expect(dispatcher.run("page.go", { n: "x" })).rejects.toBeInstanceOf(ActInvalid);
    expect(run).not.toHaveBeenCalled();
  });

  it("runs with a value that fits", async () => {
    register("page", { name: "go", input, run });

    await dispatcher.run("page.go", { n: 1 });

    expect(run).toHaveBeenCalledWith({}, { n: 1 });
  });

  it("refuses no value unless the input allows null", async () => {
    register("page", { name: "go", input, run }, { name: "maybe", input: { type: ["object", "null"] }, run });

    await expect(dispatcher.run("page.go")).rejects.toThrow("value must be an object");
    await dispatcher.run("page.maybe");
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("shows a refused click's reason in a toast and runs nothing", async () => {
    register("page", { name: "go", input, run });

    await dispatcher.perform("page.go", { n: "x" });

    expect(toast.error).toHaveBeenCalledWith("page.go: value.n must be an integer");
    expect(run).not.toHaveBeenCalled();
  });
});

describe("a described act with no input", () => {
  it("takes no value, but a null one", async () => {
    register("page", { name: "go", description: "Goes.", run });

    await expect(dispatcher.run("page.go", "x")).rejects.toThrow("this act takes no value; send none");
    await dispatcher.run("page.go", null);
    await dispatcher.run("page.go");
    expect(run).toHaveBeenCalledTimes(2);
  });

  it("with a picker and no input takes any value", async () => {
    register("page", {
      name: "go",
      description: "Goes.",
      argument: { label: "Things", options: () => [] },
      run,
    });

    await dispatcher.run("page.go", "anything");

    expect(run).toHaveBeenCalled();
  });
});

describe("an act that declares nothing", () => {
  it("takes any value: a script's act may leave its declaration out", async () => {
    register("page", { name: "go", run });

    await dispatcher.run("page.go", { whatever: 1 });

    expect(run).toHaveBeenCalledWith({}, { whatever: 1 });
  });
});

describe("a built-in act's sidecar", () => {
  it("loads on the first run, and checks the value with the text's input", async () => {
    register("shell", { name: "theme", run });
    expect(actText.loadedText("shell")).toBeUndefined();

    await expect(dispatcher.run("shell.theme", "blue")).rejects.toThrow('value must be one of "light", "dark", "system"');
    await dispatcher.run("shell.theme", "dark");

    expect(actText.loadedText("shell")).toBeDefined();
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("does not hold a click that carries no value while it loads", async () => {
    register("shell", { name: "about", run });

    void dispatcher.perform("shell.about");

    expect(run).toHaveBeenCalledTimes(1);
  });

  it("holds a click that carries a value until the sidecar has loaded", async () => {
    register("shell", { name: "theme", run });

    const clicked = dispatcher.perform("shell.theme", "blue");
    expect(run).not.toHaveBeenCalled();
    await clicked;

    expect(toast.error).toHaveBeenCalled();
    expect(run).not.toHaveBeenCalled();
  });

  it("lets a script's own input beat the sidecar's", async () => {
    register("shell", { name: "theme", input: { type: "string" }, run });

    await dispatcher.run("shell.theme", "blue");

    expect(run).toHaveBeenCalled();
  });

  it("is listed with the text by `described`, while `available` carries only what is inline", async () => {
    register("shell", { name: "theme", asks: ["picker"], run }, { name: "mine", description: "Mine.", run });

    expect(dispatcher.available().map((act) => act.description)).toEqual([undefined, "Mine."]);
    const described = await dispatcher.described();

    expect(described[0].description).toMatch(/color scheme/);
    expect(described[0].input).toMatchObject({ enum: ["light", "dark", "system"] });
    expect(described[0].asks).toEqual(["picker"]);
    expect(described[1].description).toBe("Mine.");
  });

  it("gives an unknown surface an empty sidecar", async () => {
    expect(await actText.loadText("nothing")).toEqual({});
  });
});

describe("a click on a built-in list act", () => {
  it("passes the selected rows the bulk bar sends", async () => {
    await actText.loadText("list");
    register("list", { name: "assign", run });

    await dispatcher.perform("list.assign", ["CONT-0001"]);

    expect(toast.error).not.toHaveBeenCalled();
    expect(run).toHaveBeenCalledWith({}, ["CONT-0001"]);
  });
});

describe("a sidecar that fails to load", () => {
  it("says the act could not be checked, not that it is unavailable", async () => {
    vi.spyOn(actText, "loadText").mockRejectedValue(new Error("chunk failed"));
    register("shell", { name: "go", run });

    await dispatcher.perform("shell.go", { n: 1 });

    expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("could not be checked"));
    expect(run).not.toHaveBeenCalled();
  });
});
