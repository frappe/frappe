// A tab opened before a build holds chunk names that build deleted.
import { onMounted, onUnmounted } from "vue";
import { toast } from "frappe-ui";
import { __ } from "@/i18n";

/** While the shell is mounted, a lazy chunk that fails to load shows one "new version" toast with a Reload action. */
export function useStaleBuildNotice() {
	onMounted(() => window.addEventListener("vite:preloadError", askReload));
	onUnmounted(() => window.removeEventListener("vite:preloadError", askReload));
}

// No auto-reload: it would throw away unsaved edits. The fixed id makes a later failure replace the toast.
function askReload() {
	toast(__("A new version is available"), {
		id: "stale-build",
		duration: Infinity,
		action: { label: __("Reload"), onClick: () => window.location.reload() },
	});
}
