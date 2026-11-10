import { onMounted, onUnmounted, ref, watch } from "vue";

/**
 * Mount a desk component (frappe.ui.*) inside a Vue host element.
 * `build` gets the host and returns the instance; `sources` are watched and
 * re-render it.
 */
export function useDeskWidget(build, sources = []) {
	const host = ref(null);
	const widget = ref(null);

	function render() {
		if (!host.value) return;
		host.value.replaceChildren();
		widget.value = build(host.value);
	}

	onMounted(render);
	onUnmounted(() => host.value?.replaceChildren());
	if (sources.length) watch(sources, render, { deep: true });

	return { host, widget };
}
