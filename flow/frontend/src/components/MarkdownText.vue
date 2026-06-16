<script setup>
import { ref, watch, onUnmounted } from "vue";

// Renders streamed assistant text as markdown. Parsing is coalesced to one call
// per animation frame so a fast token stream can't trigger a parse per token.
// Takes the whole part (not part.text) so the parent's render doesn't depend on
// the streaming text — only this component reacts to each token.
const props = defineProps({ part: { type: Object, required: true } });

const html = ref("");
let frame = 0;

function render() {
	frame = 0;
	const raw = props.part.text || "";
	let out = window.frappe?.markdown ? frappe.markdown(raw) : escapeHtml(raw);
	// Let a wide table scroll in its own box instead of widening the panel.
	html.value = out
		.replace(/<table(\s[^>]*)?>/g, '<div class="md-table-scroll"><table$1>')
		.replace(/<\/table>/g, "</table></div>");
}

function schedule() {
	if (frame) return;
	frame = requestAnimationFrame(render);
}

function escapeHtml(s) {
	return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

watch(() => props.part.text, schedule, { immediate: true });
onUnmounted(() => frame && cancelAnimationFrame(frame));
</script>

<template>
	<div class="md" v-html="html"></div>
</template>
