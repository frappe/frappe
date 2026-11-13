// The `layouts` acts: open another layout, and add, rename, condition, delete or reset one. The
// layout menu asks for each act's value in a dialog, then runs it with that value.
import type { ActItem } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import type { EditorActsHost } from "./editorActs";
import { newLayoutId } from "./layoutMenu";
import type { LayoutRef } from "./workingLayouts";

export interface AddedLayout {
	type: FormLayoutType;
	title: string;
	condition: string;
	start: "copy" | "empty";
}

export function layoutItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	const canvas = () => host.canvas()!;
	const editing = () => Boolean(host.canvas()?.editable);
	return [
		{
			name: "open",
			label: __("Open a layout"),
			palette: false,
			when: () => Boolean(host.canvas()),
			run: (_context, layout: LayoutRef) => open(host, layout),
		},
		{
			name: "add",
			label: __("Add a layout"),
			palette: false,
			when: editing,
			run: async (_context, layout: AddedLayout) => {
				const id = newLayoutId();
				if (await canvas().stage({ act: "layouts.add", id, ...layout })) open(host, { type: layout.type, id });
			},
		},
		{
			name: "rename",
			label: __("Rename layout"),
			palette: false,
			when: editing,
			run: (_context, keys: { layout: LayoutRef; title: string }) =>
				canvas().stage({ act: "layouts.rename", ...keys }),
		},
		{
			name: "set_condition",
			label: __("Edit layout condition"),
			palette: false,
			when: editing,
			run: (_context, keys: { layout: LayoutRef; condition: string }) =>
				canvas().stage({ act: "layouts.set_condition", ...keys }),
		},
		{
			name: "delete",
			label: __("Delete layout"),
			palette: false,
			when: editing,
			run: (_context, keys: { layout: LayoutRef }) => canvas().stage({ act: "layouts.delete", ...keys }),
		},
		{
			name: "reset_to_app",
			label: __("Reset to app layout"),
			palette: false,
			when: () => editing() && host.canvas()?.state.mode === "Customize",
			run: (_context, keys: { type: FormLayoutType }) => canvas().stage({ act: "layouts.reset_to_app", ...keys }),
		},
	];
}

function open(host: EditorActsHost, layout: LayoutRef) {
	host.canvas()!.open(layout);
	host.tab.value = "editor";
}
