// The `layouts` acts: open another layout, and add, rename, condition, delete or reset one. The
// layout menu asks for each act's value in a dialog, then runs it with that value.
import { ActDeclined, type ActCall, type ActItem } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import type { EditorActsHost } from "./editorActs";
import { confirmReset } from "./layoutDialogs";
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
			asks: ["confirm"],
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
			asks: ["confirm"],
			label: __("Rename layout"),
			palette: false,
			when: editing,
			run: (_context, keys: { layout: LayoutRef; title: string }) =>
				canvas().stage({ act: "layouts.rename", ...keys }),
		},
		{
			name: "set_condition",
			asks: ["confirm"],
			label: __("Edit layout condition"),
			palette: false,
			when: editing,
			run: (_context, keys: { layout: LayoutRef; condition: string }) =>
				canvas().stage({ act: "layouts.set_condition", ...keys }),
		},
		{
			name: "delete",
			asks: ["confirm"],
			label: __("Delete layout"),
			palette: false,
			when: editing,
			run: (_context, keys: { layout: LayoutRef }) => canvas().stage({ act: "layouts.delete", ...keys }),
		},
		{
			name: "reset_to_app",
			asks: ["confirm"],
			label: __("Reset to app layout"),
			palette: false,
			when: () => editing() && host.canvas()?.state.mode === "Customize",
			// A person's script skips the dialog, as the menu opens it first; an agent's call opens it here.
			run: async (_context, keys: { type: FormLayoutType }, call?: ActCall) => {
				if (call?.agent && !(await confirmReset(canvas(), keys.type))) throw new ActDeclined("layouts.reset_to_app");
				return canvas().stage({ act: "layouts.reset_to_app", ...keys });
			},
		},
	];
}

function open(host: EditorActsHost, layout: LayoutRef) {
	host.canvas()!.open(layout);
	host.tab.value = "editor";
}

/** An id the server takes for a new layout until its save names the row. */
export function newLayoutId(): string {
	return `new-${Math.random().toString(36).slice(2, 10)}`;
}
