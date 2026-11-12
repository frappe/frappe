<!-- The menu at a row's right-click, in a chunk of its own: the list loads it on the first one. -->
<template>
	<ContextMenu :options="options" @update:open="$event || emit('close')">
		<div
			ref="anchor"
			class="fixed size-0"
			:style="{ left: `${at?.x}px`, top: `${at?.y}px` }"
		/>
	</ContextMenu>
</template>

<script setup lang="ts">
import { ContextMenu } from "frappe-ui";
import { computed, nextTick, ref, watch } from "vue";
import { useRouter, type RouteLocationRaw } from "vue-router";
import type { ListRow } from "@/listPage/types";
import type { RowMenuOption } from "./rowActions";
import { copyLink } from "@/shell/shellActs";
import type { BulkBar } from "./useBulkBar";
import { contextMenuOptions } from "./rowContextMenu";
import type { ContextMenuAt } from "./useRowContextMenu";

const props = defineProps<{
	at: ContextMenuAt | null;
	rows: ListRow[];
	selection: string[];
	rowMenu: (row: ListRow) => RowMenuOption[];
	bulk: BulkBar;
	rowLink: (row: ListRow) => RouteLocationRaw;
}>();
const emit = defineEmits<{ close: [] }>();

const router = useRouter();
const anchor = ref<HTMLElement>();

const options = computed(() => {
	const row = props.rows.find((one) => one.name === props.at?.row);
	if (!row) return [];
	const href = router.resolve(props.rowLink(row)).href;
	return contextMenuOptions({
		row,
		selection: props.selection,
		rowOptions: props.rowMenu(row),
		layout: props.bulk.layout.value,
		open: () => router.push(props.rowLink(row)),
		openInNewTab: () => void window.open(href, "_blank", "noopener"),
		copyLink: () => void copyLink(new URL(href, window.location.origin).href),
	});
});

// The menu opens where a contextmenu event lands, so the anchor replays one at the pointer.
watch(
	() => props.at,
	async (at) => {
		if (!at) return;
		await nextTick();
		anchor.value?.dispatchEvent(
			new MouseEvent("contextmenu", {
				bubbles: true,
				cancelable: true,
				clientX: at.x,
				clientY: at.y,
			})
		);
	},
	{ immediate: true }
);
</script>
