// The merge & ordering rules as executable claims.
import { afterEach, describe, expect, it, vi } from "vitest";
import { isReactive, nextTick, watchEffect } from "vue";
import { Surface } from "../surface";
import { HeaderSurface } from "../headerRenderings";
import {
	HEADER_ITEM_KEYS,
	PANEL_SECTION_KEYS,
	QUICK_ACTION_KEYS,
	TAB_ITEM_KEYS,
} from "../types";
import { registerRecordPage, registrationsFor, resetRegistry } from "../registry";
import { withRegisteringSource } from "../context";

function names(surface: Surface) {
	return surface.visible().map((item) => item.name);
}

function builtins(surface: Surface, ...list: string[]) {
	surface.provideBuiltins(() => list.map((name) => ({ name, label: name })));
}

describe("surface verbs", () => {
	it("appends an add without a position and splices one with an anchor", () => {
		const surface = new Surface();
		builtins(surface, "email", "print");
		surface.add({ name: "convert" });
		surface.add({ name: "dial" }, { before: "print" });
		expect(names(surface)).toEqual(["email", "dial", "print", "convert"]);
	});

	it("degrades an unknown anchor to append", () => {
		const surface = new Surface();
		builtins(surface, "email");
		surface.add({ name: "dial" }, { before: "missing" });
		expect(names(surface)).toEqual(["email", "dial"]);
	});

	it("hides reversibly and never deletes", () => {
		const surface = new Surface();
		builtins(surface, "email", "print");
		surface.hide("email");
		expect(names(surface)).toEqual(["print"]);
		surface.show("email");
		expect(names(surface)).toEqual(["email", "print"]);
	});

	it("replaces a colliding name in place, keeping the slot", () => {
		const surface = new Surface();
		builtins(surface, "email", "print");
		surface.add({ name: "convert" }, { before: "print" });
		surface.add({ name: "convert", label: "Rewritten" });
		expect(names(surface)).toEqual(["email", "convert", "print"]);
		expect(surface.visible()[1].label).toBe("Rewritten");
	});

	it("orders listed names to the front, unlisted keep their relative order", () => {
		const surface = new Surface();
		builtins(surface, "email", "comment", "print", "attach");
		surface.add({ name: "convert" });
		surface.order(["convert", "email", "missing"]);
		expect(names(surface)).toEqual(["convert", "email", "comment", "print", "attach"]);
	});

	it("does not re-enforce an earlier order over a later add", () => {
		const surface = new Surface();
		builtins(surface, "email", "print");
		surface.order(["print", "email"]);
		surface.add({ name: "late" }, { before: "email" });
		expect(names(surface)).toEqual(["print", "late", "email"]);
	});

	it("updates shallow-merge into the item", () => {
		const surface = new Surface();
		builtins(surface, "email");
		surface.update("email", { label: "Email the customer" });
		expect(surface.visible()[0].label).toBe("Email the customer");
	});

	it("resets to built-ins alone on replay", () => {
		const surface = new Surface();
		builtins(surface, "email");
		surface.add({ name: "convert" });
		surface.hide("email");
		surface.beginReplay();
		surface.commitReplay();
		expect(names(surface)).toEqual(["email"]);
	});

	it("resolves over the built-ins as they are now, not as they were", () => {
		const surface = new Surface();
		let tags = true;
		surface.provideBuiltins(() =>
			["email", ...(tags ? ["tags"] : [])].map((name) => ({ name })),
		);
		surface.order(["tags", "email"]);
		expect(names(surface)).toEqual(["tags", "email"]);
		tags = false;
		expect(names(surface)).toEqual(["email"]);
	});
});

// A replay used to clear the ops and re-add them a microtask later, so a keyless
// `v-for` rebuilt the strip and lost the reader's place. These are the staged replay's rules.
describe("props on an item", () => {
	it("keeps a component inside props raw, as it keeps the item's component", () => {
		const Icon = { render: () => null };
		const surface = new Surface();
		surface.add({ name: "badge", props: { icon: Icon, size: "sm" } });
		const [item] = surface.visible();
		expect(isReactive(item.props.icon)).toBe(false);
		expect(item.props.size).toBe("sm");
	});
});

describe("clear", () => {
	it("hides every item present at the call, and keeps each one addressable", () => {
		const surface = new Surface();
		builtins(surface, "email", "print");
		surface.add({ name: "convert" });
		surface.clear();
		expect(names(surface)).toEqual([]);
		expect(surface.has("email")).toBe(true);
		expect(surface.has("convert")).toBe(true);
	});

	it("is an op in source order: a later add draws and a later show brings one back", () => {
		const surface = new Surface();
		builtins(surface, "email", "print");
		surface.clear();
		surface.add({ name: "banner" });
		surface.show("print");
		expect(names(surface)).toEqual(["print", "banner"]);
	});

	it("leaves the items a later source adds untouched", async () => {
		const surface = new Surface();
		builtins(surface, "email");
		await withRegisteringSource("first", async () => surface.clear());
		await withRegisteringSource("second", async () => surface.add({ name: "banner" }));
		expect(names(surface)).toEqual(["banner"]);
	});
});

describe("staged replay", () => {
	it("never renders the middle of a replay", async () => {
		const surface = new Surface();
		builtins(surface, "email");
		surface.add({ name: "convert" });

		const seen: string[][] = [];
		const stop = watchEffect(() => seen.push(names(surface)));
		await nextTick();

		surface.beginReplay();
		await nextTick(); // where the old `reset()` flushed a strip of built-ins alone
		surface.add({ name: "convert" });
		surface.commitReplay();
		await nextTick();
		stop();

		expect(seen.length).toBeGreaterThan(0);
		for (const render of seen) expect(render).toEqual(["email", "convert"]);
	});

	it("starts the replay from built-ins, so a dropped op does not survive it", () => {
		const surface = new Surface();
		builtins(surface, "email");
		surface.add({ name: "convert" });
		surface.beginReplay();
		surface.add({ name: "dial" });
		surface.commitReplay();
		expect(names(surface)).toEqual(["email", "dial"]);
	});

	it("renders an op recorded outside a replay immediately", () => {
		const surface = new Surface();
		builtins(surface, "email");
		surface.beginReplay();
		surface.commitReplay();
		// A `run` handler, an `onTabChange`, a quick-action callback.
		surface.add({ name: "dial" });
		expect(names(surface)).toEqual(["email", "dial"]);
	});

	it("tells a source about its own work mid-replay, and only its own", () => {
		const surface = new Surface();
		builtins(surface, "email");
		surface.add({ name: "convert" });
		surface.beginReplay();
		// Last replay's `convert` is gone from the source's view the moment the
		// new one opens, even though it is still what the host renders.
		expect(surface.has("convert")).toBe(false);
		expect(names(surface)).toEqual(["email", "convert"]);
		surface.add({ name: "dial" });
		expect(surface.has("dial")).toBe(true);
		expect(names(surface)).toEqual(["email", "convert"]);
	});

	it("publishes only on the outermost commit of a nested replay", () => {
		const surface = new Surface();
		builtins(surface, "email");
		surface.beginReplay();
		surface.add({ name: "convert" });
		// A script calling `page.refresh()` from its own `refresh` handler.
		surface.beginReplay();
		surface.add({ name: "dial" });
		surface.commitReplay();
		expect(names(surface)).toEqual(["email"]);
		surface.add({ name: "print" });
		surface.commitReplay();
		expect(names(surface)).toEqual(["email", "dial", "print"]);
	});

	it("ignores a commit with no replay open", () => {
		const surface = new Surface();
		builtins(surface, "email");
		surface.add({ name: "convert" });
		surface.commitReplay();
		expect(names(surface)).toEqual(["email", "convert"]);
	});
});

// The promise in COMPATIBILITY.md, per surface: a key the engine does not read is
// dropped, and a development build says so once.
describe("a key the engine does not read", () => {
	afterEach(() => {
		vi.restoreAllMocks();
		vi.unstubAllEnvs();
	});

	const surfaces: [string, readonly string[], () => Surface][] = [
		["quickActions", QUICK_ACTION_KEYS, () => new Surface({ surface: "quickActions", keys: QUICK_ACTION_KEYS })],
		["header", HEADER_ITEM_KEYS, () => new HeaderSurface()],
		["tabs", TAB_ITEM_KEYS, () => new Surface({ surface: "tabs", keys: TAB_ITEM_KEYS })],
		["panelSections", PANEL_SECTION_KEYS, () => new Surface({ surface: "panelSections", keys: PANEL_SECTION_KEYS })],
	];

	for (const [name, keys, make] of surfaces) {
		it(`${name}.add drops it, warns once, and keeps the rest`, () => {
			const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
			const surface = make();
			surface.add({ name: "x", label: "X", variant: "subtle" });
			surface.add({ name: "x", label: "X", variant: "subtle" });
			expect(surface.find("x")).toEqual({ name: "x", label: "X" });
			expect(warn).toHaveBeenCalledTimes(1);
			expect(warn.mock.calls[0][0]).toBe(
				`[record-page] ${name}.add('x'): key 'variant' is not one the engine reads — dropped.`,
			);
		});

		it(`${name}.update drops it from the patch and warns`, () => {
			const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
			const surface = make();
			surface.add({ name: "x", label: "X" });
			surface.update("x", { label: "Y", variant: "subtle" });
			expect(surface.find("x")).toEqual({ name: "x", label: "Y" });
			expect(warn).toHaveBeenCalledTimes(1);
			expect(warn.mock.calls[0][0]).toContain(`${name}.update('x'): key 'variant'`);
		});

		it(`${name} stays quiet on every key it reads`, () => {
			const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
			const surface = make();
			const item = Object.fromEntries(keys.map((key) => [key, key === "name" ? "x" : `v-${key}`]));
			surface.add(item as any);
			surface.update("x", { label: "Y" });
			expect(warn).not.toHaveBeenCalled();
			expect(Object.keys(surface.find("x")!).sort()).toEqual([...keys].sort());
		});
	}

	it("warns once per item and key, so a second item with the same key is named too", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const surface = new Surface({ surface: "tabs", keys: TAB_ITEM_KEYS });
		surface.add({ name: "x", label: "X", variant: "subtle" });
		surface.add({ name: "y", label: "Y", variant: "subtle" });
		surface.update("x", { variant: "ghost" });
		expect(warn).toHaveBeenCalledTimes(2);
	});

	it("checks every item of a block, and a patch staged inside a replay", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const surface = new Surface({ surface: "tabs", keys: TAB_ITEM_KEYS });
		surface.add([{ name: "x", label: "X" }, { name: "y", label: "Y", variant: "subtle" }]);
		surface.beginReplay();
		surface.add({ name: "x", label: "X" });
		surface.update("x", { label: "Z", variant: "ghost" });
		expect(surface.find("x")).toEqual({ name: "x", label: "Z" });
		surface.commitReplay();
		expect(surface.find("x")).toEqual({ name: "x", label: "Z" });
		expect(warn.mock.calls.map((call) => call[0])).toEqual([
			"[record-page] tabs.add('y'): key 'variant' is not one the engine reads — dropped.",
			"[record-page] tabs.update('x'): key 'variant' is not one the engine reads — dropped.",
		]);
	});

	it("keeps every key on a surface with no vocabulary", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const surface = new Surface();
		surface.add({ name: "x", variant: "subtle" });
		expect(surface.find("x")).toEqual({ name: "x", variant: "subtle" });
		expect(warn).not.toHaveBeenCalled();
	});

	it("drops the key in production too, and says nothing", () => {
		vi.stubEnv("DEV", false);
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const surface = new Surface({ surface: "tabs", keys: TAB_ITEM_KEYS });
		surface.add({ name: "x", label: "X", variant: "subtle" });
		expect(surface.find("x")).toEqual({ name: "x", label: "X" });
		expect(warn).not.toHaveBeenCalled();
	});
});

describe("registry run order", () => {
	it("keeps sources in registration order, generic before specific within one", async () => {
		resetRegistry();
		registerRecordPage("CRM Deal", { onRefresh: () => {} });
		registerRecordPage("*", { onRefresh: () => {} });
		await withRegisteringSource("audit", async () => {
			registerRecordPage("CRM Deal", { onRefresh: () => {} });
		});
		const order = registrationsFor("CRM Deal").map(
			(registration) => `${registration.source}:${registration.doctype}`,
		);
		expect(order).toEqual(["host:*", "host:CRM Deal", "audit:CRM Deal"]);
		resetRegistry();
	});
});
