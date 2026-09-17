<template>
	<!-- Display-only, sanitized render. Mirrors the sanitize-before-render convention
	     `HtmlField` uses. The container always renders for a preview-capable language
	     (even when empty) so the consumer's min-height/border holds instead of
	     collapsing; every other language renders nothing. -->
	<!-- eslint-disable-next-line vue/no-v-html -->
	<div
		v-if="isPreviewLanguage"
		class="prose prose-sm max-w-none text-ink-gray-8"
		v-html="sanitized"
	/>
</template>

<script setup lang="ts">
// Preview half of the code field, separate from the writer:
//   markdown → marked() → sanitizeHtml → v-html
//   html     → sanitizeHtml → v-html
// Any other language renders nothing. No emit — display only.
//
// It used to be `CodePreview` in `frappe-ui/experimental`. The v1 code-editor
// family dropped it, because a markdown renderer is not a code editor, and the
// migration guide says each app keeps its own copy. This is that copy.
import { computed } from "vue";
import { marked } from "marked";
import { sanitizeHtml } from "../../utils/sanitize";

const props = defineProps<{
	modelValue?: string;
	/** A `fieldtypeToLanguage` key. Only `markdown` and `html` render anything. */
	language?: string;
}>();

const isPreviewLanguage = computed(
	() => props.language === "markdown" || props.language === "html"
);

const sanitized = computed(() => {
	const src = props.modelValue ?? "";
	if (!src) return "";
	// `marked.parse` is sync for string input — no async extensions are registered.
	if (props.language === "markdown") return sanitizeHtml(marked.parse(src) as string);
	if (props.language === "html") return sanitizeHtml(src);
	return "";
});
</script>
