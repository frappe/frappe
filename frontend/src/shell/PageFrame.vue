<!--
  A generated page's root: the pinned header row and, unless `scroll=false`, the scroll region.
  The page owns the row's contents, its top and bottom padding, and its max width.
-->
<template>
	<!-- The header is declared inside the viewport, so its click-to-top finds this page's scroll. -->
	<ScrollArea v-if="scroll" class="min-h-0 flex-1" :viewportClass="pageGutter">
		<PageHeader v-if="headed">
			<slot name="header"><PageHeaderTitle :title="title" /></slot>
		</PageHeader>
		<slot />
	</ScrollArea>

	<!-- No padding here: a pane that scrolls both ways puts the gutter on its own viewport. -->
	<div v-else class="flex min-h-0 flex-1 flex-col overflow-hidden">
		<PageHeader v-if="headed">
			<slot name="header"><PageHeaderTitle :title="title" /></slot>
		</PageHeader>
		<slot />
	</div>
</template>

<script lang="ts">
/** The side padding a page's content shares with the header row: `PageHeader`'s own classes. */
export const pageGutter = "px-3 sm:px-5";
</script>

<script setup lang="ts">
import { computed, useSlots } from "vue";
import { PageHeader, PageHeaderTitle, ScrollArea } from "frappe-ui";

const props = withDefaults(
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

const slots = useSlots();

// Without a `PageHeader` the shell's target keeps no height.
const headed = computed(() => !!props.title || !!slots.header);
</script>
