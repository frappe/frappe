// The bulk bar's collaboration actions: the built-in items, and the one request a dialog opens with.
import { computed, ref, type Ref } from "vue";
import type { BulkSelection } from "@framework/ui/api";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { __ } from "@/i18n";
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

interface Spec {
	label: string;
	icon: string;
	right: string;
	button?: boolean;
	needs?: "follow" | "track_seen";
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
	follow: () => ({ label: __("Follow"), icon: "lucide-bell", right: "read", needs: "follow" }),
	unfollow: () => ({ label: __("Unfollow"), icon: "lucide-bell-off", right: "read", needs: "follow" }),
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

export interface BulkCollaboration {
	/** The built-in items for `provideBuiltins`. */
	items: () => ListPageAction[];
	/** Set by an item's `run`; the list mounts the lazy dialog while it holds one. */
	request: Ref<CollabRequest | null>;
	/** Whether `run` is one of these items': they send the bar's whole scope, so "all matching" keeps them enabled. */
	takesScope: (run: unknown) => boolean;
}

// The doctypes `_follow_document` refuses beside the log types, so Follow is hidden where the server never follows.
const NEVER_FOLLOWED = new Set([
	"Communication",
	"ToDo",
	"Email Unsubscribe",
	"File",
	"Comment",
	"Email Account",
	"Email Domain",
	"Version",
	"Error Log",
	"Scheduled Job Log",
	"Event Sync Log",
	"Event Update Log",
	"Access Log",
	"View Log",
	"Activity Log",
	"Energy Point Log",
	"Notification Log",
	"Email Queue",
	"DocShare",
	"Document Follow",
	"Console Log",
]);

/** `user` is the session user: the server does not let Administrator follow. */
export function useBulkCollaboration(doctype: string, target: () => BulkTarget, user: string): BulkCollaboration {
	const { meta } = useDoctypeMeta(doctype);
	const tracks = computed(() => {
		const tracked = meta.value as { track_changes?: number; track_seen?: number; issingle?: number } | null;
		return {
			follow: Boolean(tracked?.track_changes) && !NEVER_FOLLOWED.has(doctype) && user !== "Administrator",
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
