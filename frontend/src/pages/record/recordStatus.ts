// The header's `status` item: the workflow state when the doctype has one, else the docstatus of a submittable.
import { __ } from "@/i18n";
import type { HeaderItem } from "@/recordPage";
import { workflowTheme } from "@/statusTheme";
import RecordStatus from "./RecordStatus.vue";

const DOCSTATUS = [
	{ label: "Draft", theme: "gray" },
	{ label: "Submitted", theme: "blue" },
	{ label: "Cancelled", theme: "red" },
] as const;

/** Empty when the record has no status to show. */
export function statusItems(meta: any, doc: Record<string, any>): HeaderItem[] {
	const state = meta?.workflow_state_field ? doc[meta.workflow_state_field] : undefined;
	if (state) return [status(String(state), workflowTheme(meta, String(state)))];
	if (!meta?.is_submittable) return [];
	const { label, theme } = DOCSTATUS[doc.docstatus ?? 0] ?? DOCSTATUS[0];
	return [status(__(label), theme)];
}

function status(label: string, theme: string): HeaderItem {
	return { name: "status", label, zone: "left", component: RecordStatus, props: { label, theme } };
}
