// The merge & ordering rules as executable claims.
import { describe, expect, it } from "vitest";
import { nextTick, watchEffect } from "vue";
import { Surface } from "../surface";
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
