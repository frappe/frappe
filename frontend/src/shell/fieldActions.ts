// The field actions an app placed in its `field-actions.js`, handed to the controls in `ui/` by
// `FieldActionsKey`. Each item names an act; the act's label, icon and right are its defaults and gate.
import { shallowRef } from "vue";
import type { FieldAction, FieldActions, FieldMeta } from "@framework/ui/fields/types";
import { fieldActionFiles } from "@/contributions/registry";
import type { FieldActionItem } from "@/contributions/types";
import { acts } from "@/acts/dispatcher";
import { emailFieldAction, type EmailOpeners } from "./emailFieldAction";

/** The apps' field action items, imported once when the first reader asks. */
export class FieldActionItems {
	private loaded = shallowRef<FieldActionItem[]>([]);
	private loading: Promise<void> | undefined;

	/** Reactive: empty until the apps' files are in. */
	list(): FieldActionItem[] {
		if (!fieldActionFiles.length) return [];
		this.loading ??= importAll().then((all) => void (this.loaded.value = all));
		return this.loaded.value;
	}
}

export const fieldActionItems = new FieldActionItems();

/** The shell side of field actions: apps' files are imported when the first control asks. */
export function fieldActions(emailOpeners: EmailOpeners, items: FieldActionItems = fieldActionItems): FieldActions {
	return {
		for(field, value, record) {
			if (!hasValue(value)) return [];
			const own = emailFieldAction(field, value, record, emailOpeners);
			return [...own, ...items.list().filter((item) => item.fieldtype === kindOf(field)).flatMap((item) => button(item, value))];
		},
	};
}

/** A Data field whose options say Phone is a Phone to the apps. */
export function kindOf(field: FieldMeta) {
	return field.fieldtype === "Data" && field.options === "Phone" ? "Phone" : field.fieldtype;
}

function hasValue(value: unknown): value is string {
	return typeof value === "string" && value.trim() !== "";
}

// Hidden by the act's right (or by being absent) means no button, not a disabled one.
function button(item: FieldActionItem, value: string): FieldAction[] {
	if (item.when && !item.when(value)) return [];
	const act = acts.find(item.act);
	if (!act) return [];
	const label = item.label ?? act.label ?? item.act;
	const icon = item.icon ?? act.icon;
	return [{ act: item.act, label, icon, run: () => void acts.perform(item.act, item.value ? item.value(value) : value) }];
}

async function importAll(): Promise<FieldActionItem[]> {
	const files = [...fieldActionFiles];
	const results = await Promise.allSettled(files.map((file) => file.load()));
	return results.flatMap((result, index) => {
		const { app } = files[index];
		if (result.status === "rejected") {
			console.error(`[frappe] ${app}'s field-actions.js did not load; it adds no action.`, result.reason);
			return [];
		}
		return itemsOf(app, result.value.default);
	});
}

function itemsOf(app: string, exported: unknown): FieldActionItem[] {
	if (!Array.isArray(exported)) {
		warn(`${app}'s field-actions.js has no list as its default export; it adds no action.`);
		return [];
	}
	return exported.filter((item) => {
		const valid = typeof item?.act === "string" && typeof item.fieldtype === "string";
		if (!valid) warn(`${app}'s field-actions.js holds an entry with no act or no fieldtype; it is ignored.`);
		return valid;
	});
}

function warn(message: string) {
	console.warn(`[frappe] ${message}`);
}
