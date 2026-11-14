// What the editor calls each layout type, and the open layout on the layout crumb.
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import { __ } from "@/i18n";
import type { LayoutRef, WorkingLayout } from "./workingLayouts";

export function typeLabel(type: FormLayoutType): string {
	return LABELS[type]();
}

/** The open type's label, or the open conditional layout's title, else its condition. */
export function openLayoutName(open: LayoutRef, layout: WorkingLayout | null): string {
	if (!layout) return typeLabel("Details");
	return layout.condition ? layout.title || layout.condition : typeLabel(open.type);
}

const LABELS: Record<FormLayoutType, () => string> = {
	Details: () => __("Details"),
	"Side Panel": () => __("Side panel"),
	"Quick Entry": () => __("Quick entry"),
	"New Record": () => __("New record"),
};
