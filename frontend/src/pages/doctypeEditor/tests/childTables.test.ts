// The child tables' loads: a slow one overtaken by a later `show`, and one that started for a parent that has since reloaded.
import { beforeEach, expect, it, vi } from "vitest";
import type { EditorState } from "../editorSource";
import { mountEditor, taskNote } from "./editorFixture";

const loads = new Map<string, (state: EditorState) => void>();

vi.mock("../editorSource", async (importOriginal) => ({
	...(await importOriginal<typeof import("../editorSource")>()),
	loadEditor: (doctype: string) => new Promise<EditorState>((resolve) => loads.set(doctype, resolve)),
}));

const parent = () =>
	taskNote({
		definition: {
			...taskNote().definition,
			fields: [
				{ fieldname: "lines", label: "Lines", fieldtype: "Table", options: "Line" },
				{ fieldname: "notes", label: "Notes", fieldtype: "Table", options: "Note Line" },
			],
		},
	} as Partial<EditorState>);
const child = (doctype: string) => taskNote({ doctype, definition: { name: doctype, fields: [] } } as Partial<EditorState>);

beforeEach(() => loads.clear());

it("opens only the latest show when an earlier child loads last", async () => {
	const { children } = mountEditor(parent());
	const first = children.show("lines");
	const second = children.show("notes");
	loads.get("Note Line")!(child("Note Line"));
	await second;
	loads.get("Line")!(child("Line"));
	await first;
	expect(children.open.value?.state.doctype).toBe("Note Line");
});

it("keeps no child that a reset overtook", async () => {
	const { children } = mountEditor(parent());
	const shown = children.show("lines");
	children.reset();
	loads.get("Line")!(child("Line"));
	await shown;
	expect(children.canvasOf("Line")).toBeNull();
	expect(children.open.value).toBeNull();
});

it("keeps a child that a later show for another table overtook", async () => {
	const { children } = mountEditor(parent());
	const first = children.show("lines");
	const second = children.show("notes");
	loads.get("Line")!(child("Line"));
	await first;
	expect(children.canvasOf("Line")).not.toBeNull();
	loads.get("Note Line")!(child("Note Line"));
	await second;
});
