<template>
	<!-- Display-only, sanitized render. The container always renders for a preview-capable
	     language, even when empty, so the consumer's min-height and border hold instead of
	     collapsing; any other language renders nothing. -->
	<!-- eslint-disable-next-line vue/no-v-html -->
	<div
		v-if="isPreviewLanguage"
		class="prose prose-sm max-w-none text-ink-gray-8"
		v-html="sanitized"
	/>
</template>

<script setup lang="ts">
// Markdown/HTML preview of the code field: marked (markdown only), then DOMPurify, then v-html.
import DOMPurify from "dompurify";
import { marked } from "marked";
import { computed } from "vue";

const props = defineProps<{
	modelValue?: string;
	language?: string;
}>();

const isPreviewLanguage = computed(
	() => props.language === "markdown" || props.language === "html"
);

const sanitized = computed(() => {
	const src = props.modelValue ?? "";
	if (!src) return "";
	if (props.language === "markdown") {
		// `marked.parse` is sync for string input; no async extensions are registered.
		return DOMPurify.sanitize(marked.parse(src) as string);
	}
	if (props.language === "html") {
		return DOMPurify.sanitize(src);
	}
	return "";
});
</script>
