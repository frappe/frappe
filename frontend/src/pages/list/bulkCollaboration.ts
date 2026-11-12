// The bulk bar's collaboration actions: the built-in items, and the one request a dialog opens with.
import { computed, ref, type Ref } from "vue";
import type { BulkPart, BulkSelection } from "@framework/ui/api";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { __, __n } from "@/i18n";
import type { ListPageAction } from "@/listPage/types";

export type CollabKind =
	| "assign"
	| "clear_assignment"
	| "apply_assignment_rule"
	| "add_tags"
	| "remove_tags"
	| "follow"
	| "unfollow"
	| "share"
	| "mark_seen"
	| "mark_unseen";

/** The records a run takes, as the bar's scope states them. */
export interface BulkTarget {
	selection: BulkSelection;
	count: number;
	/** Every record the filters show, not the selected rows. */
	all: boolean;
	/** The count is a floor ("10,000+"). */
	approx: boolean;
}

/** What the dialog opens with: the target frozen at the click, so a changed selection cannot change the run. */
export interface CollabRequest extends BulkTarget {
	kind: CollabKind;
}

export interface CollabCall {
	part: BulkPart;
	method: "POST" | "DELETE";
	/** The body beside the selection, one call per entry. */
	bodies: Record<string, unknown>[];
}

interface Spec {
	label: string;
	icon: string;
	right: string;
	button?: boolean;
	needs?: "track_changes" | "track_seen";
}

const SPECS: Record<CollabKind, () => Spec> = {
	assign: () => ({ label: __("Assign to…"), icon: "lucide-user-plus", right: "write", button: true }),
	clear_assignment: () => ({ label: __("Clear assignment"), icon: "lucide-user-x", right: "write" }),
	apply_assignment_rule: () => ({
		label: __("Apply assignment rule"),
		icon: "lucide-shuffle",
		right: "write",
	}),
	add_tags: () => ({ label: __("Add tags"), icon: "lucide-tag", right: "write", button: true }),
	remove_tags: () => ({ label: __("Remove tags"), icon: "lucide-tags", right: "write" }),
	follow: () => ({ label: __("Follow"), icon: "lucide-bell", right: "read", needs: "track_changes" }),
	unfollow: () => ({ label: __("Unfollow"), icon: "lucide-bell-off", right: "read", needs: "track_changes" }),
	share: () => ({ label: __("Share"), icon: "lucide-share-2", right: "share" }),
	mark_seen: () => ({ label: __("Mark as seen"), icon: "lucide-eye", right: "read", needs: "track_seen" }),
	mark_unseen: () => ({
		label: __("Mark as unseen"),
		icon: "lucide-eye-off",
		right: "read",
		needs: "track_seen",
	}),
};

export function kindLabel(kind: CollabKind): string {
	return SPECS[kind]().label;
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

export interface BulkCollaboration {
	/** The built-in items for `provideBuiltins`. */
	items: () => ListPageAction[];
	/** Set by an item's `run`; the list mounts the lazy dialog while it holds one. */
	request: Ref<CollabRequest | null>;
	/** Whether `run` is one of these items': they send the bar's whole scope, so "all matching" keeps them enabled. */
	takesScope: (run: unknown) => boolean;
}

export function useBulkCollaboration(doctype: string, target: () => BulkTarget): BulkCollaboration {
	const { meta } = useDoctypeMeta(doctype);
	const tracks = computed(() => {
		const tracked = meta.value as { track_changes?: number; track_seen?: number; issingle?: number } | null;
		return {
			track_changes: Boolean(tracked?.track_changes),
			track_seen: Boolean(tracked?.track_seen) && !tracked?.issingle,
		};
	});
	const request = ref<CollabRequest | null>(null);

	const kinds = Object.keys(SPECS) as CollabKind[];
	const runs = new Map(kinds.map((kind) => [kind, () => void (request.value = { kind, ...target() })]));

	function items(): ListPageAction[] {
		return kinds.map((kind) => {
			const { label, icon, right, button, needs } = SPECS[kind]();
			return {
				name: kind,
				label,
				icon,
				group: "collaborate",
				right,
				button,
				when: needs ? () => tracks.value[needs] : undefined,
				run: runs.get(kind),
			};
		});
	}

	return { items, request, takesScope: (run) => [...runs.values()].some((candidate) => candidate === run) };
}
