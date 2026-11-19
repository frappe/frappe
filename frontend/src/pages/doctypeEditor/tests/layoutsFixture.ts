// A standard "Lead Note" with a layout of every kind: app Details entries under a site row, no
// Side Panel, a Quick Entry fallback and a New Record that reads Details.
import type { EditorLayout, EditorState } from "../editorSource";
import type { LayoutTree } from "@/recordPage/formLayoutSource/types";
import { taskNote } from "./editorFixture";

export const tabs = (...fields: string[]): LayoutTree => [
	{ name: "first_tab", sections: [{ name: "main", columns: [{ name: "column_1", fields }] }] },
];

export function leadNote(overrides: Partial<EditorState> = {}): EditorState {
	const base = taskNote();
	const layouts: Record<string, EditorLayout[]> = {
		Details: [
			{ name: "FL-1", source: "site", condition: null, omitted: [], layout: tabs("subject") },
			{ name: null, source: "app", condition: null, omitted: [], layout: tabs("subject", "status") },
			{
				name: null,
				source: "app",
				title: "Done",
				condition: "doc.status == 'Done'",
				omitted: [],
				layout: tabs("subject"),
			},
		],
		"Side Panel": [{ name: null, source: "none", condition: null, omitted: [], layout: null as never }],
		"Quick Entry": [{ name: null, source: "fallback", condition: null, omitted: [], layout: tabs("notes") }],
		"New Record": [{ name: null, source: "same as Details", condition: null, omitted: [], layout: null as never }],
	};
	return {
		...base,
		doctype: "Lead Note",
		custom: 0,
		modes: ["Design", "Customize"],
		layouts,
		definition: { ...base.definition, name: "Lead Note", custom: 0 },
		...overrides,
	};
}
