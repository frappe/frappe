import { h } from "vue";

type Row = { label?: string; description?: string; theme?: string; disabled?: boolean; slots?: object };

/** A menu row that names its act: frappe-ui's menu rows take no attrs, so the mark rides on the label slot, drawn as the default label is. */
export function withAct<T extends Row>(row: T, act: string): T & { slots: object } {
	return marked(row, { "data-act": act });
}

/** A menu row that only opens a submenu: the same mark `data-view` gives a button. */
export function withView<T extends Row>(row: T): T & { slots: object } {
	return marked(row, { "data-view": "" });
}

function marked<T extends Row>(row: T, mark: Record<string, string>) {
	// The slot's `item` is the row as the menu draws it, so a theme set after wrapping still shows.
	const label = (context?: { item?: Row }) => {
		const item = context?.item ?? row;
		const color = item.disabled ? "text-ink-gray-4" : item.theme === "red" ? "text-ink-red-7" : "text-ink-gray-7";
		return h("div", { class: "min-w-0", ...mark }, [
			h("div", { class: ["truncate leading-tighter", color] }, item.label),
			item.description && h("div", { class: "truncate text-p-sm text-ink-gray-5" }, item.description),
		]);
	};
	return { ...row, slots: { ...row.slots, label } };
}
