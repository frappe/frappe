// The bar's status actions: Submit and Cancel on a submittable doctype, and the workflow transitions common to the selection.
import { bulkWorkflowActions, type BulkSelection, type BulkStatusRoute } from "@framework/ui/api";
import { computed, onScopeDispose, ref, shallowRef, watch, type ComputedRef, type Ref, type ShallowRef } from "vue";
import { __, __n } from "@/i18n";
import type { ListMeta } from "@/list/defaults";
import type { BulkScope } from "@/list/useBulkScope";
import type { ListPageAction } from "@/listPage/types";

const TRANSITIONS_DEBOUNCE_MS = 300;

export interface BulkStatusAction {
	route: BulkStatusRoute;
	label: string;
	transition?: string;
	/** What the request takes, frozen when the person asked. */
	body: BulkSelection;
	scope: string;
}

export interface BulkStatus {
	items: ComputedRef<ListPageAction[]>;
	/** Whether `run` is one of the items' own: they take the whole scope, not the loaded rows. */
	owns: (run: ListPageAction["run"]) => boolean;
	asked: ShallowRef<BulkStatusAction | null>;
	/** Reads the common actions again: a run moves the selection to new states. */
	refresh: () => void;
	/** A run ended: re-reads the common actions and reloads the list. */
	finished: () => void;
	/** Puts these names in the selection, for the result panel's "Select failed". */
	select: (names: string[]) => void;
}

export interface BulkStatusOptions {
	doctype: string;
	meta: Ref<ListMeta | null | undefined>;
	selection: Ref<string[]>;
	scope: BulkScope;
	cap: number;
	locked: boolean;
	reload: () => void;
}

export function useBulkStatus({ doctype, meta, selection, scope, cap, locked, reload }: BulkStatusOptions): BulkStatus {
	const asked = shallowRef<BulkStatusAction | null>(null);
	const transitions = shallowRef<string[]>([]);
	const refreshed = ref(0);
	const ask = (action: Omit<BulkStatusAction, "body" | "scope">) =>
		(asked.value = { ...action, body: scope.selected(), scope: wording() });
	const wording = () =>
		scope.all.value
			? __n("all {0} matching record", "all {0} matching records", scope.total.value, [scope.totalText.value])
			: __n("{0} selected record", "{0} selected records", scope.count.value, [scope.count.value]);

	const hasWorkflow = computed(() => Boolean(meta.value?.workflow_state_field));
	const submittable = computed(() => Boolean(meta.value?.is_submittable) && !hasWorkflow.value);
	followTransitions();

	const items = computed<ListPageAction[]>(() => [
		...transitions.value.map((transition) => ({
			name: `workflow-${transition.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "-")}`,
			label: __(transition),
			group: "workflow" as const,
			run: () => ask({ route: "bulk_workflow", label: __(transition), transition }),
		})),
		...(submittable.value
			? [
					{
						name: "submit",
						label: __("Submit"),
						icon: "lucide-badge-check",
						group: "danger" as const,
						right: "submit",
						run: () => ask({ route: "bulk_submit", label: __("Submit") }),
					},
					{
						name: "cancel",
						label: __("Cancel"),
						icon: "lucide-ban",
						group: "danger" as const,
						right: "cancel",
						run: () => ask({ route: "bulk_cancel", label: __("Cancel") }),
					},
			  ]
			: []),
	]);

	/** Reads the actions common to the selection once it settles; a reply for an older selection is dropped. */
	function followTransitions() {
		let timer: ReturnType<typeof setTimeout> | undefined;
		let latest = 0;
		watch(
			[() => JSON.stringify(scope.selected()), () => scope.count.value, hasWorkflow, refreshed],
			() => {
				clearTimeout(timer);
				const read = ++latest;
				transitions.value = [];
				if (locked || !hasWorkflow.value || !scope.count.value || scope.count.value > cap) return;
				const body = scope.selected();
				timer = setTimeout(async () => {
					const { data } = await bulkWorkflowActions(doctype, body).catch(() => ({ data: [] }));
					if (read === latest) transitions.value = data;
				}, TRANSITIONS_DEBOUNCE_MS);
			},
			{ immediate: true }
		);
		onScopeDispose(() => clearTimeout(timer));
	}

	const refresh = () => refreshed.value++;
	// A run over all matching moves records out of the list, as Delete's does: the scope ends with it.
	const finished = () => {
		if (scope.all.value) scope.clear();
		refresh();
		reload();
	};
	const select = (names: string[]) => (selection.value = names);
	const owns = (run: ListPageAction["run"]) => items.value.some((item) => item.run === run);
	return { items, owns, asked, refresh, finished, select };
}
