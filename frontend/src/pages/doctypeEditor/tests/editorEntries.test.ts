import { describe, expect, it } from "vitest";
import { editorEntries } from "../entries/editorEntries";

const manager = ["System Manager", "All"];
const names = (entries: { name: string }[]) => entries.map((entry) => entry.name);

describe("editorEntries", () => {
	it("offers Customize form to a System Manager on a standard DocType outside developer mode", () => {
		const entries = editorEntries("Sales Invoice", { roles: manager, developerMode: false });
		expect(names(entries)).toEqual(["customize_form"]);
		expect(entries[0].mode).toBe("Customize");
	});

	it("adds Edit DocType in developer mode", () => {
		const entries = editorEntries("Sales Invoice", { roles: manager, developerMode: true });
		expect(names(entries)).toEqual(["customize_form", "edit_doctype"]);
		expect(entries[1].mode).toBe("Design");
	});

	it("offers only Edit DocType on a custom DocType, which always opens in Design", () => {
		const entries = editorEntries("Task Note", { roles: manager, developerMode: false, custom: true });
		expect(names(entries)).toEqual(["edit_doctype"]);
	});

	it("keeps Customize form off a Single", () => {
		const entries = editorEntries("Print Settings", { roles: manager, developerMode: false, single: true });
		expect(names(entries)).toEqual([]);
	});

	it("offers nothing without the System Manager role", () => {
		expect(editorEntries("Sales Invoice", { roles: ["Accounts User"], developerMode: true })).toEqual([]);
	});
});
