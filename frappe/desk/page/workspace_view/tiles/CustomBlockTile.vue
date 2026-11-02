<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";

// A site's Custom HTML Block, in its own shadow root so its styles stay in and the page's stay
// out. Desk's CSS variables still inherit. The script runs with the viewer's authority, as it
// always has; only a manager's block can be shared.
const props = defineProps({
	widget: { type: Object, required: true },
});

const host = ref(null);
let root = null;

onMounted(() => {
	if (!host.value) return;
	root = host.value.attachShadow({ mode: "open" });

	const body = document.createElement("div");
	body.innerHTML = window.frappe.dom.remove_script_and_style(props.widget.html || "");
	const style = document.createElement("style");
	style.textContent = props.widget.style || "";
	root.append(body, style);

	try {
		new Function("root_element", props.widget.script || "")(root);
	} catch (e) {
		console.error(`custom block "${props.widget.label}" failed`, e);
	}
});

// A script that mounted an island never gets a hook to unmount it, so the tile does.
onBeforeUnmount(() => {
	for (const el of root?.querySelectorAll("*") || []) window.frappe.ui.unmount_island(el);
});
</script>

<template>
	<div v-if="!widget.html && !widget.script" class="p-4 text-base text-ink-gray-5">
		{{ widget.label }}
	</div>
	<div v-else ref="host" class="ws-custom-block" />
</template>
