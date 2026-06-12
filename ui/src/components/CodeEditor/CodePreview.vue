<template>
	<!-- Display-only, sanitized render. Mirrors `HtmlField`'s sanitize-before-render
	     convention (DOMPurify is a transitive frappe-ui dep). The container always
	     renders for a preview-capable language (even when empty) so the consumer's
	     min-height/border holds instead of collapsing; non-preview languages render
	     nothing. -->
	<!-- eslint-disable-next-line vue/no-v-html -->
	<div
		v-if="isPreviewLanguage"
		class="prose prose-sm max-w-none text-ink-gray-8"
		v-html="sanitized"
	/>
</template>

<script setup lang="ts">
// Preview primitive — separate from the writer. Renders read-only sanitized
// output for the two languages that have a meaningful preview:
//   markdown → marked() → DOMPurify.sanitize → v-html
//   html     → DOMPurify.sanitize → v-html
// Any other language renders nothing (the wrapper only mounts this for fieldtypes
// that want a preview). No emit — display only.
import { computed } from "vue";
import DOMPurify from "dompurify";
import { marked } from "marked";
import type { CodePreviewProps } from "./types";

const props = defineProps<CodePreviewProps>();

const isPreviewLanguage = computed(
	() => props.language === "markdown" || props.language === "html"
);

const sanitized = computed(() => {
	const src = props.modelValue ?? "";
	if (!src) return "";
	if (props.language === "markdown") {
		// `marked.parse` is sync for string input (no async extensions here).
		return DOMPurify.sanitize(marked.parse(src) as string);
	}
	if (props.language === "html") {
		return DOMPurify.sanitize(src);
	}
	return "";
});
</script>
