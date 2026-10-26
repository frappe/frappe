<script setup>
import { computed } from "vue";

// Stored text drawn as legacy draws it: a header translates its inner text, a paragraph its
// whole HTML. Both arrive sanitized from the server.
const props = defineProps({
	block: { type: Object, required: true },
});

const __ = window.__;

const html = computed(() => with_user(translated()));

function translated() {
	const text = __(props.block.data.text || "");
	if (props.block.type !== "header") return text;
	if (!/<[a-z][\s\S]*>/i.test(text)) return `<span class="h4">${text}</span>`;

	const inner = new DOMParser().parseFromString(text, "text/html").body.textContent;
	const escaped = window.frappe.utils.escape_html(inner);
	return text.replace(escaped, __(escaped));
}

// `{first_name}`, `{last_name}` and `{full_name}` greet whoever is reading
function with_user(text) {
	const { escape_html } = window.frappe.utils;
	const user = window.frappe.boot.user || {};
	const full_name = window.frappe.session.user_fullname || "";
	return text
		.replaceAll("{first_name}", escape_html(user.first_name || full_name))
		.replaceAll("{last_name}", escape_html(user.last_name || ""))
		.replaceAll("{full_name}", escape_html(full_name));
}
</script>

<template>
	<div class="ws-text" :class="block.type === 'header' ? 'pt-2' : ''" v-html="html" />
</template>

<style scoped>
/* legacy's workspace sizes, weights and inks */
.ws-text {
	color: var(--ink-gray-5);
	font-size: 14px;
	line-height: 1.6;
	overflow-wrap: anywhere;
}

.ws-text :deep(:is(.h1, .h2, .h3, .h4, .h5, .h6)) {
	line-height: 1.2;
	font-weight: 700;
}

.ws-text :deep(:is(.h1, .h2, .h3, .h6)) {
	color: var(--ink-gray-9);
}

.ws-text :deep(.h1) {
	font-size: 28px;
}

.ws-text :deep(.h2) {
	font-size: 24px;
}

.ws-text :deep(.h3) {
	font-size: 20px;
}

.ws-text :deep(.h4) {
	font-size: 16px;
}

.ws-text :deep(.h5) {
	font-size: 14px;
}

.ws-text :deep(.h6) {
	font-size: 11px;
}

.ws-text :deep(b) {
	font-weight: 700;
}

.ws-text :deep(a) {
	text-decoration: underline;
}
</style>
