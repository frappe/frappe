// The `fields` acts of Table fields and their child tables: pick or make the child, open its
// editor, and move a field, which also moves its grid column.
import type { ActItem } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { EditorActsHost } from "./editorActs";

export function childFieldItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	const editing = () => host.tab.value === "editor" && Boolean(host.canvas()?.editable);
	return [
		{
			name: "add_child_table",
			label: __("New child table"),
			palette: false,
			when: editing,
			run: (_context, keys: { name: string; table_field: string; label?: string; link?: string }) =>
				host.canvas()!.stage({ ...keys, act: "fields.add_child_table" }),
		},
		{
			name: "open_child",
			label: __("Edit child table"),
			palette: false,
			when: () => Boolean(host.openChild),
			run: (_context, table: string) => host.openChild!(table),
		},
		{
			name: "reorder_field",
			label: __("Move field"),
			palette: false,
			when: editing,
			run: (_context, keys: { fieldname: string; index: number }) =>
				host.canvas()!.stage({ ...keys, act: "fields.reorder_field" }),
		},
	];
}
