// The layout menu's acts that need a value: each asks in a dialog, then runs its `layouts` act.
import { defineAsyncComponent } from "vue";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import { shellDialog } from "@/shell/dialog";
import type { DesignCanvas } from "./designCanvas";
import type { AddedLayout } from "./layoutActs";
import { resetSummary, resetWording, typeLabel, type LayoutMenu, type OpenLayoutAct } from "./layoutMenu";

const AddLayoutDialog = defineAsyncComponent(() => import("./AddLayoutDialog.vue"));
const LayoutTextDialog = defineAsyncComponent(() => import("./LayoutTextDialog.vue"));
const ResetLayoutDialog = defineAsyncComponent(() => import("./ResetLayoutDialog.vue"));

export async function addLayout(canvas: DesignCanvas, menu: LayoutMenu) {
	const types = menu.types.map(({ type, label }) => ({ value: type, label }));
	const layout: AddedLayout | null = await shellDialog().open(
		AddLayoutDialog,
		{ working: canvas.working.value, types, type: canvas.openLayout.value.type },
		{ title: __("Add a layout") }
	);
	if (layout) await acts.perform("layouts.add", layout);
}

export async function runOpenLayoutAct(canvas: DesignCanvas, act: OpenLayoutAct) {
	const layout = canvas.openLayout.value;
	if (act === "delete") return acts.perform("layouts.delete", { layout });
	if (act === "reset_to_app") return resetToApp(canvas, layout.type);
	const open = canvas.layout.value!;
	if (act === "rename") {
		const title = await askText(__("Rename layout"), {
			label: __("Title"),
			value: open.title ?? "",
			confirmLabel: __("Rename"),
		});
		if (title !== null) await acts.perform("layouts.rename", { layout, title });
		return;
	}
	const condition = await askText(__("Edit condition"), {
		label: __("Show it when"),
		value: open.condition ?? "",
		placeholder: "doc.status == 'Open'",
		description: __("JavaScript on doc, as in Depends On."),
		confirmLabel: __("Save condition"),
	});
	if (condition !== null) await acts.perform("layouts.set_condition", { layout, condition });
}

/** Asks first, listing the site layouts the reset removes. */
export async function resetToApp(canvas: DesignCanvas, type: FormLayoutType) {
	const working = canvas.working.value;
	const { title, confirmLabel } = resetWording(working, type);
	const props = { label: typeLabel(type), summary: resetSummary(working, type), confirmLabel };
	const reset = await shellDialog().open(ResetLayoutDialog, props, { title });
	if (reset) await acts.perform("layouts.reset_to_app", { type });
}

function askText(title: string, props: Record<string, string>): Promise<string | null> {
	return shellDialog().open(LayoutTextDialog, props, { title });
}
