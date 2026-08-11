// The merge & ordering rules (wayfinder ticket 06) as executable claims.
import { describe, expect, it } from "vitest";
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
		surface.reset();
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

describe("registry run order", () => {
	it("keeps sources in registration order, generic before specific within one", async () => {
		resetRegistry();
		registerRecordPage("CRM Deal", { refresh: () => {} });
		registerRecordPage("*", { refresh: () => {} });
		await withRegisteringSource("audit", async () => {
			registerRecordPage("CRM Deal", { refresh: () => {} });
		});
		const order = registrationsFor("CRM Deal").map(
			(registration) => `${registration.source}:${registration.doctype}`,
		);
		expect(order).toEqual(["host:*", "host:CRM Deal", "audit:CRM Deal"]);
		resetRegistry();
	});
});
