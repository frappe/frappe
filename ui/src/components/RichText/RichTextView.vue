<template>
	<div class="rich-text-view prose prose-sm max-w-none" v-html="safe" />
</template>

<script setup lang="ts">
// Stored rich text drawn without the editor, so it costs none of the editor's chunk.
import { computed, shallowRef, watchEffect } from "vue";
import { sanitizeHtml } from "../../utils/sanitize";
import { drawCodeBlocks, hasCodeBlock, loadHighlighter, type Highlighter } from "./codeBlocks";

const props = defineProps<{ html: string | null | undefined }>();

const highlighter = shallowRef<Highlighter | null>(null);

// A `<style>` element in a stored value would restyle the whole page.
const safe = computed(() => {
	const html = hasCodeBlock(props.html)
		? drawCodeBlocks(props.html!, highlighter.value)
		: props.html;
	return sanitizeHtml(html, { FORBID_TAGS: ["style"] });
});

watchEffect(async () => {
	if (!highlighter.value && hasCodeBlock(props.html))
		highlighter.value = await loadHighlighter();
});
</script>

<style>
/* The editor's node views, drawn as plain markup: mentions, media, and code blocks. */
.rich-text-view .ql-editor > :first-child {
	@apply mt-0;
}
.rich-text-view .ql-editor > :last-child {
	@apply mb-0;
}
.rich-text-view .mention {
	@apply inline-block px-px font-semibold hover:bg-surface-gray-1;
	border-radius: 4px;
	box-decoration-break: clone;
}

.rich-text-view :is(img, video) {
	@apply my-2 mr-auto rounded-4;
}
.rich-text-view :is(video:not([data-align]), :is(img, video)[data-align="center"]) {
	@apply mx-auto;
}
.rich-text-view :is(img, video)[data-align="right"] {
	@apply ml-auto mr-0;
}
.rich-text-view :is(img, video)[data-float="left"] {
	@apply float-left m-2 mr-5;
}
.rich-text-view :is(img, video)[data-float="right"] {
	@apply float-right m-2 ml-5;
}

.rich-text-view pre.code-block {
	@apply flex items-start gap-5 border border-outline-gray-2 py-3 pl-3 pr-4;
	border-radius: 0.75rem;
	background: #f6f8fa;
	color: #24292e;
	font-family: ui-monospace, Menlo, Monaco, "Cascadia Mono", "Segoe UI Mono", "Roboto Mono",
		"Oxygen Mono", "Ubuntu Mono", "Source Code Pro", "Fira Mono", "Droid Sans Mono", "Consolas",
		"Courier New", monospace;
	font-size: 12px;
	line-height: 1.7;
}
[data-theme="dark"] .rich-text-view pre.code-block {
	background: #0d1117;
	color: #c9d1d9;
}
.rich-text-view .code-block-lines {
	@apply flex flex-none select-none flex-col items-end text-ink-gray-4;
}
.rich-text-view pre.code-block code {
	@apply min-w-0 flex-1 overflow-x-auto;
	color: inherit;
	font-size: inherit;
	line-height: inherit;
}
</style>
