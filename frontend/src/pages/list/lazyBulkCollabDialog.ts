// The bulk collaboration dialog as a lazy chunk, for each surface that draws the bar.
import { toast } from "frappe-ui";
import { defineAsyncComponent } from "vue";
import { __ } from "@/i18n";

export function lazyBulkCollabDialog(dismiss: () => void) {
	return defineAsyncComponent({
		loader: () => import("./BulkCollabDialog.vue"),
		onError: (_error, _retry, fail) => {
			toast.error(__("The dialog did not load. Reload the page and try again."));
			dismiss();
			fail();
		},
	});
}
