// What the collaboration dialog sends and says: the calls a kind makes and the records it names. Only the lazy dialog imports it.
import type { BulkPart } from "@framework/ui/api";
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
