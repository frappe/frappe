// `list.assign` with users: the bulk dialog's assignment, sent at once and reported by the shell as the dialog's is.
import { isBulkQueued, type BulkQueued, type BulkResult } from "@framework/ui/api";
import { ActInvalid } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { runBulk } from "@/shell/bulkOutcome";
import type { BulkTarget } from "./bulkCollaboration";

/** What the act answers: the records now assigned, the ones that failed, and whether the server took the run to the background. */
export interface Assigned {
	assigned: string[];
	failed: BulkResult["failed"];
	background: boolean;
}

interface AfterRun {
	reload: () => void;
	select: (names: string[]) => void;
}

export async function assignUsers(
	users: string[],
	doctype: string,
	target: BulkTarget,
	after: AfterRun
): Promise<Assigned> {
	if (!Array.isArray(users) || !users.length || users.some((user) => typeof user !== "string" || !user.trim()))
		throw new ActInvalid("list.assign", "users must be a list of user ids; send none to open the dialog");
	if (!target.count) throw new ActInvalid("list.assign", "no rows are selected; select rows first");
	const { callsFor, sendCollab } = await import("./collabCalls");
	const calls = callsFor("assign", { users: [...new Set(users)] });
	let answer!: BulkResult | BulkQueued;
	await runBulk({
		label: __("Assign"),
		doctype,
		send: async (names) => {
			const reply = await sendCollab(doctype, calls, names ? { names } : target.selection, after.reload);
			answer = reply.data;
			return reply;
		},
		select: after.select,
		finished: after.reload,
	});
	if (isBulkQueued(answer)) return { assigned: [], failed: [], background: true };
	return { assigned: answer.done, failed: answer.failed, background: false };
}
