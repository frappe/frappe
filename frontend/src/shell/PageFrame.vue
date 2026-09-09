<!--
  A generated page's root: the pinned header row and, unless `scroll=false`, the scroll region.
  The page owns the row's contents, its top and bottom padding, and its max width.
-->
<template>
	<!-- Read in the template, not a computed: the slots object is not reactive, and a page can
	     supply its header after mount. Without a `PageHeader` the shell's target keeps no height. -->
	<ScrollArea
		v-if="scroll"
		class="min-h-0 flex-1"
		:class="gutterVar"
		:viewportClass="pageGutter"
	>
		<PageHeader v-if="title || $slots.header">
			<slot name="header"><PageHeaderTitle :title="title" /></slot>
		</PageHeader>
		<slot />
	</ScrollArea>

	<!-- No padding here: a pane that scrolls both ways puts the gutter on its own viewport. -->
	<div v-else class="flex min-h-0 flex-1 flex-col overflow-hidden" :class="gutterVar">
		<PageHeader v-if="title || $slots.header">
			<slot name="header"><PageHeaderTitle :title="title" /></slot>
		</PageHeader>
		<slot />
	</div>
</template>

<script lang="ts">
/** The side padding a page's content shares with the header row; the frame root sets `--page-gutter`. */
export const pageGutter = "px-[--page-gutter]";
const gutterVar = "[--page-gutter:0.75rem] sm:[--page-gutter:1.25rem]";
</script>

<script setup lang="ts">
import { PageHeader, PageHeaderTitle, ScrollArea } from "frappe-ui";

withDefaults(
	defineProps<{
		/** Rendered as the row's title; the `header` slot replaces the row's whole content. */
		title?: string;
		/** `false` hands the scroll to the page: a list that scrolls both ways, a record in panes. */
		scroll?: boolean;
	}>(),
	{ scroll: true }
);

defineSlots<{
	header?: () => unknown;
	default?: () => unknown;
}>();
</script>
