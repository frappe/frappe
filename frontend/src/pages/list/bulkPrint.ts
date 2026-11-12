// The list's bulk Print: the cap check, the dialog (a lazy chunk) and the records it prints behind one seam.
import type { BulkPrintBody } from "@framework/ui/api";
import { toast } from "frappe-ui";
import { defineAsyncComponent, inject, ref, type Ref } from "vue";
import type { Boot } from "@/boot";
import type { BulkScope } from "@/list/useBulkScope";
import { __, __n } from "@/i18n";

export const PrintDialog = defineAsyncComponent({
	loader: () => import("./PrintDialog.vue"),
	onError: (_error, _retry, fail) => {
		toast.error(__("The print dialog did not load. Reload the page and try again."));
		fail();
	},
});

export interface BulkPrint {
	/** The dialog stays mounted once asked, so its close animation plays. */
	mounted: Ref<boolean>;
	open: Ref<boolean>;
	/** The records the open dialog prints, frozen when it was asked. */
	scope: Ref<BulkPrintBody>;
	count: Ref<number>;
	all: Ref<boolean>;
	approx: Ref<boolean>;
	ask: () => void;
}

export function useBulkPrint(bulk: BulkScope): BulkPrint {
	const boot = inject<Boot>("boot")!;
	const mounted = ref(false);
	const open = ref(false);
	const scope = ref<BulkPrintBody>({});
	const count = ref(0);
	const all = ref(false);
	const approx = ref(false);

	function ask() {
		const cap = boot.max_bulk_print_docs;
		if (cap && bulk.count.value > cap) {
			toast.error(
				__n("You can print up to {0} record at a time", "You can print up to {0} records at a time", cap, [cap])
			);
			return;
		}
		scope.value = bulk.selected();
		count.value = bulk.count.value;
		all.value = bulk.all.value;
		approx.value = bulk.approx.value;
		mounted.value = open.value = true;
	}

	return { mounted, open, scope, count, all, approx, ask };
}
