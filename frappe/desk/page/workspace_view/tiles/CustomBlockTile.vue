<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

// A site's Custom HTML Block, in its own shadow root so its styles stay in and the page's stay
// out. Desk's CSS variables still inherit. The script runs with the viewer's authority, as it
// always has; only a manager's block can be shared.
const props = defineProps({
	widget: { type: Object, required: true },
});

const host = ref(null);
const source = computed(() => (props.widget.record_changed ? props.widget.record : props.widget));
let root = null;

// A script that mounted an island never gets a hook to unmount it, so the tile does.
function unmount_islands() {
	for (const el of root?.querySelectorAll("*") || []) window.frappe.ui.unmount_island(el);
}

function draw() {
	unmount_islands();
	const body = document.createElement("div");
	body.innerHTML = window.frappe.dom.remove_script_and_style(source.value.html || "");
	const style = document.createElement("style");
	style.textContent = source.value.style || "";
	root.replaceChildren(body, style);

	try {
		new Function("root_element", source.value.script || "")(root);
	} catch (e) {
		console.error(`custom block "${props.widget.label}" failed`, e);
	}
}

onMounted(() => {
	root = host.value.attachShadow({ mode: "open" });
	draw();
});

watch(
	() => [source.value.html, source.value.style, source.value.script],
	window.frappe.utils.debounce(draw, 400)
);

onBeforeUnmount(unmount_islands);
</script>

<template>
	<div v-if="!source.html && !source.script" class="p-4 text-base text-ink-gray-5">
		{{ widget.label }}
	</div>
	<div v-show="source.html || source.script" ref="host" class="ws-custom-block" />
</template>
