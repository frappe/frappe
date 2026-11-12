// What the collaboration dialog sends and says: the calls a kind makes and the records it names. Only the lazy dialog imports it.
import {
	bulkCollaborate,
	isBulkQueued,
	type BulkPart,
	type BulkQueued,
	type BulkResult,
	type BulkSelection,
	type Envelope,
} from "@framework/ui/api";
import { followBulkRun } from "@/shell/bulkRuns";
import { __, __n } from "@/i18n";
import type { BulkTarget, CollabKind } from "./bulkCollaboration";

export interface CollabCall {
	part: BulkPart;
	method: "POST" | "DELETE";
	/** The body beside the selection, one call per entry. */
	bodies: Record<string, unknown>[];
}

/** The records a confirmation names: "12 selected records", or "all 340 matching records". */
export function scopeText({ count, all, approx }: Pick<BulkTarget, "count" | "all" | "approx">): string {
	const shown = approx ? `${count}+` : String(count);
	if (all) return __("all {0} matching records", [shown]);
	return __n("{0} selected record", "{0} selected records", count, [shown]);
}

/** The calls a kind makes; `users`, `tags`, `colors` and `canWrite` are what its dialog collected. */
export function callsFor(
	kind: CollabKind,
	input: { users?: string[]; tags?: string[]; colors?: Record<string, string>; canWrite?: boolean }
): CollabCall[] {
	const { users = [], tags = [], colors = {}, canWrite = false } = input;
	switch (kind) {
		case "assign":
			return [{ part: "assignments", method: "POST", bodies: users.map((user) => ({ user })) }];
		case "clear_assignment":
			return [{ part: "assignments", method: "DELETE", bodies: [{}] }];
		case "apply_assignment_rule":
			return [{ part: "assignment_rule", method: "POST", bodies: [{}] }];
		case "add_tags":
			return [
				{
					part: "tags",
					method: "POST",
					bodies: tags.map((tag) => ({ tag, ...(colors[tag] ? { color: colors[tag] } : {}) })),
				},
			];
		case "remove_tags":
			return [{ part: "tags", method: "DELETE", bodies: tags.map((tag) => ({ tag })) }];
		case "follow":
			return [{ part: "follows", method: "POST", bodies: [{}] }];
		case "unfollow":
			return [{ part: "follows", method: "DELETE", bodies: [{}] }];
		case "share":
			return [
				{
					part: "shares",
					method: "POST",
					bodies: users.map((user) => ({ user, write: canWrite ? 1 : 0 })),
				},
			];
		case "mark_seen":
			return [{ part: "seen", method: "POST", bodies: [{}] }];
		case "mark_unseen":
			return [{ part: "seen", method: "DELETE", bodies: [{}] }];
	}
}

/** Sends every call of a kind over one selection and answers them as one run, so the shell reports it once. */
export async function sendCollab(
	doctype: string,
	calls: CollabCall[],
	selection: BulkSelection,
	reload: () => void
): Promise<Envelope<BulkResult | BulkQueued>> {
	const replies: Envelope<BulkResult | BulkQueued>[] = [];
	for (const { part, method, bodies } of calls)
		for (const body of bodies) replies.push(await bulkCollaborate(doctype, part, method, selection, body));
	const queued = replies.filter(({ data }) => isBulkQueued(data));
	// The shell follows the first background run; the others settle on their own and reload the list.
	for (const { data } of queued.slice(1)) followBulkRun((data as BulkQueued).task_id, reload);
	if (queued.length) return queued[0];
	const runs = replies.map(({ data }) => data as BulkResult);
	const failed = runs.flatMap((run) => run.failed).filter(({ name }, at, all) => all.findIndex((one) => one.name === name) === at);
	const failedNames = new Set(failed.map(({ name }) => name));
	return { ...replies[0], data: { ...runs[0], done: runs[0].done.filter((name) => !failedNames.has(name)), failed } };
}
