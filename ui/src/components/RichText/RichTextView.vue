<template>
	<div class="rich-text-view prose prose-sm max-w-none" v-html="safe" />
</template>

<script setup lang="ts">
// Stored rich text drawn without the editor, so it costs none of the editor's chunk.
import { computed, shallowRef, watchEffect } from "vue";
import { sanitizeHtml } from "../../utils/sanitize";
import { drawHtml, hasCodeBlock, loadHighlighter, type Highlighter } from "./drawHtml";

const props = defineProps<{ html: string | null | undefined }>();

const highlighter = shallowRef<Highlighter | null>(null);

// A stored `<style>` would restyle the whole page; a stored form could post off-site.
const safe = computed(() =>
	sanitizeHtml(props.html ? drawHtml(props.html, highlighter.value) : props.html, {
		FORBID_TAGS: ["style", "form"],
		FORBID_ATTR: ["form", "formaction"],
		ADD_ATTR: ["target"],
	})
);

watchEffect(() => {
	if (highlighter.value || !hasCodeBlock(props.html)) return;
	loadHighlighter().then(
		(loaded) => (highlighter.value = loaded),
		() => {}
	);
});
</script>

<style>
/* Stored inline styles can position content; keep it inside the view. */
.rich-text-view {
	contain: paint;
}
/* Desk v1 wrapped every value in one div, so prose's own first and last child rules miss. */
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
.rich-text-view [data-type="image-group"] {
	@apply my-2 grid grid-cols-4 gap-2;
}
.rich-text-view [data-type="image-group"][data-columns="2"] {
	@apply grid-cols-2;
}
.rich-text-view [data-type="image-group"][data-columns="3"] {
	@apply grid-cols-3;
}
.rich-text-view [data-type="image-group"] img {
	@apply m-0 aspect-square h-full w-full rounded-4 object-cover;
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
