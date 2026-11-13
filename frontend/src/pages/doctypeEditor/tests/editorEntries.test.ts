import { describe, expect, it } from "vitest";
import { editorEntries } from "../entries/editorEntries";

const manager = ["System Manager", "All"];
const standard = { custom: 0, issingle: 0 };
const names = (entries: { name: string }[]) => entries.map((entry) => entry.name);

describe("editorEntries", () => {
	it("offers Customize form to a System Manager on a standard DocType outside developer mode", () => {
		const entries = editorEntries("Sales Invoice", { roles: manager, developerMode: false, meta: standard });
		expect(names(entries)).toEqual(["customize_form"]);
		expect(entries[0].mode).toBe("Customize");
	});

	it("adds Edit DocType in developer mode", () => {
		const entries = editorEntries("Sales Invoice", { roles: manager, developerMode: true, meta: standard });
		expect(names(entries)).toEqual(["customize_form", "edit_doctype"]);
		expect(entries[1].mode).toBe("Design");
	});

	it("offers only Edit DocType on a custom DocType, which always opens in Design", () => {
		const entries = editorEntries("Task Note", { roles: manager, developerMode: false, meta: { custom: 1 } });
		expect(names(entries)).toEqual(["edit_doctype"]);
	});

	it("keeps Customize form off a Single", () => {
		const entries = editorEntries("Print Settings", { roles: manager, developerMode: false, meta: { issingle: 1 } });
		expect(names(entries)).toEqual([]);
	});

	it("keeps Customize form off a core DocType, which mode.py refuses", () => {
		expect(names(editorEntries("User", { roles: manager, developerMode: false, meta: standard }))).toEqual([]);
		expect(names(editorEntries("Client Script", { roles: manager, developerMode: true, meta: standard }))).toEqual(["edit_doctype"]);
	});

	it("offers nothing before the meta loads", () => {
		expect(editorEntries("Sales Invoice", { roles: manager, developerMode: true, meta: null })).toEqual([]);
	});

	it("offers nothing without the System Manager role", () => {
		expect(editorEntries("Sales Invoice", { roles: ["Accounts User"], developerMode: true, meta: standard })).toEqual([]);
	});
});
