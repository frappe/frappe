<script setup>
import { ref, watch, onUnmounted } from "vue";

// Renders streamed assistant text as markdown. Parsing the full accumulated
// string is O(n), so doing it per token (or per frame) is O(n²) over a long
// response. Instead we throttle to one parse per THROTTLE_MS, with a guaranteed
// trailing parse so the final text always renders in full.
// Takes the whole part (not part.text) so the parent's render doesn't depend on
// the streaming text — only this component reacts to each token.
const props = defineProps({ part: { type: Object, required: true } });

const THROTTLE_MS = 100;
const html = ref("");
let timer = 0;
let last = 0;

function render() {
	timer = 0;
	last = performance.now();
	const raw = props.part.text || "";
	let out = window.frappe?.markdown ? frappe.markdown(raw) : escapeHtml(raw);
	// Let a wide table scroll in its own box instead of widening the panel.
	html.value = out
		.replace(/<table(\s[^>]*)?>/g, '<div class="md-table-scroll"><table$1>')
		.replace(/<\/table>/g, "</table></div>");
}

function schedule() {
	// A pending timer will read the freshest text when it fires, so coalesce.
	if (timer) return;
	const elapsed = performance.now() - last;
	if (elapsed >= THROTTLE_MS) render();
	else timer = setTimeout(render, THROTTLE_MS - elapsed);
}

function escapeHtml(s) {
	return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

watch(() => props.part.text, schedule, { immediate: true });
onUnmounted(() => timer && clearTimeout(timer));
</script>

<template>
	<div class="md" v-html="html"></div>
</template>
