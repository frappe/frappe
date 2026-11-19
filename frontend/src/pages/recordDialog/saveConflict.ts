// The record dialog's answer to a save the server refused as stale: say who saved and what
// changed, and reload the record only when the reader agrees. Nothing is re-applied.
import type { ApiError } from "@framework/ui/api";
import { __ } from "@/i18n";
import type { Confirm } from "@/pages/record/discardChanges";
import { personOf } from "@/pages/record/panel/context";
import { loadRecord } from "@/pages/record/recordSource";
import { changedFields, confirmRecordConflict } from "@/pages/record/saveResponse";

export interface ConflictContext {
	doctype: string;
	name: string;
	doc: Record<string, any>;
	saved: Record<string, any>;
	fields: Parameters<typeof changedFields>[2];
	reload: () => Promise<void>;
}

export async function resolveSaveConflict(_: ApiError, confirm: Confirm, ctx: ConflictContext) {
	const latest = await loadRecord(ctx.doctype, ctx.name).catch(() => null);
	const editor = latest
		? personOf(latest.docinfo, latest.document.modified_by).name
		: __("Someone else");
	const changed = changedFields(ctx.doc, ctx.saved, ctx.fields);
	if (await confirmRecordConflict(confirm, editor, changed)) await ctx.reload();
}
