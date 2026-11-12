// The bar's status actions: Submit and Cancel on a submittable doctype, and the workflow transitions common to the selection.
import { bulkWorkflowActions, type BulkSelection, type BulkStatusRoute } from "@framework/ui/api";
import { computed, onScopeDispose, ref, shallowRef, watch, type ComputedRef, type Ref, type ShallowRef } from "vue";
import { __, __n } from "@/i18n";
import type { ListMeta } from "@/list/defaults";
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
	cap: number;
	locked: boolean;
	reload: () => void;
}

export function useBulkStatus({ doctype, meta, selection, cap, locked, reload }: BulkStatusOptions): BulkStatus {
	const asked = shallowRef<BulkStatusAction | null>(null);
	const transitions = shallowRef<string[]>([]);
	const refreshed = ref(0);
	const selected = (): BulkSelection => ({ names: [...selection.value] });
	const scope = () =>
		__n("{0} selected record", "{0} selected records", selection.value.length, [selection.value.length]);
	const ask = (action: Omit<BulkStatusAction, "body" | "scope">) =>
		(asked.value = { ...action, body: selected(), scope: scope() });

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
			[() => selection.value.join("\n"), hasWorkflow, refreshed],
			() => {
				clearTimeout(timer);
				const read = ++latest;
				transitions.value = [];
				if (locked || !hasWorkflow.value || !selection.value.length || selection.value.length > cap) return;
				timer = setTimeout(async () => {
					const { data } = await bulkWorkflowActions(doctype, selected()).catch(() => ({ data: [] }));
					if (read === latest) transitions.value = data;
				}, TRANSITIONS_DEBOUNCE_MS);
			},
			{ immediate: true }
		);
		onScopeDispose(() => clearTimeout(timer));
	}

	const refresh = () => refreshed.value++;
	const finished = () => {
		refresh();
		reload();
	};
	const select = (names: string[]) => (selection.value = names);
	return { items, asked, refresh, finished, select };
}
