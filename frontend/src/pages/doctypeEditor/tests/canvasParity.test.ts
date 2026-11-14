import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { LayoutTree } from "@/recordPage/formLayoutSource/types";
import { CANVAS_ACTS, type FlatEdit } from "../editorModel";
import { layoutFromFields } from "../fieldsLayout";
import { assignNames, EditRefused, LayoutTreeEditor } from "../layoutTree";

// The server replays the same file in `frappe/desk/doctype_editor/test_ts_parity.py`.
const fixture = JSON.parse(
	readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../../../../../frappe/desk/doctype_editor/canvas_edits_fixture.json"), "utf8"),
) as {
	base: LayoutTree;
	cases: { case: string; edits: FlatEdit[]; expected?: LayoutTree; refused?: string }[];
	from_fields: { case: string; fields: never[]; expected: LayoutTree }[];
	slugs: [string, string][];
};

/** What survives the wire: `undefined` keys drop out, as they do in the server's JSON. */
const wire = <T>(value: T): T => JSON.parse(JSON.stringify(value));

function replay(tabs: LayoutTree, edits: FlatEdit[]) {
	const tree = new LayoutTreeEditor(tabs);
	for (const edit of edits) (tree[CANVAS_ACTS[edit.act]] as (edit: FlatEdit) => void)(edit);
}

describe("canvas edits, as the server applies them", () => {
	it.each(fixture.cases)("$case", ({ edits, expected, refused }) => {
		const tabs = structuredClone(fixture.base);
		if (refused) {
			expect(() => replay(tabs, edits)).toThrow(EditRefused);
			expect(() => replay(structuredClone(fixture.base), edits)).toThrow(refused);
		} else {
			replay(tabs, edits);
			expect(wire(tabs)).toEqual(expected);
		}
	});

	it.each(fixture.slugs)("names a node labelled %j %j", (label, name) => {
		const nodes: { name?: string; label?: string }[] = [{ label }];
		assignNames(nodes, "tab");
		expect(nodes[0].name).toBe(name);
	});

	it("gives a taken name its position", () => {
		const nodes: { name?: string; label?: string }[] = [{ name: "main" }, { label: "Main" }, { label: "Main" }];
		assignNames(nodes, "section");
		expect(nodes.map((node) => node.name)).toEqual(["main", "main_2", "main_3"]);
	});

	it.each(fixture.from_fields)("builds the fallback layout: $case", ({ fields, expected }) => {
		expect(wire(layoutFromFields(fields))).toEqual(expected);
	});
});
