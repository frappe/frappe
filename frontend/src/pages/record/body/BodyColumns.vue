<!-- The body row: `page.body`'s visible columns side by side, each with its own scroll,
     a separator between neighbours, and a drag edge on a fixed column facing a flex one. -->
<template>
	<div ref="root" class="flex min-h-0 flex-1" data-record-body>
		<template v-for="(column, at) in drawn" :key="column.item.name">
			<ColumnEdge
				v-if="column.edge === 'left'"
				v-bind="edgeProps(column)"
				v-model:dragging="dragging[column.item.name]"
				@toggle="toggle(column)"
				@resize="live[column.item.name] = $event"
				@update:width="settle(column.item.name, $event)"
			/>

			<BodyColumn
				:column="column"
				:separator="at > 0"
				:dragging="dragging[column.item.name] === true"
			>
				<template #default="{ collapsed }">
					<slot
						v-if="$slots[column.item.name]"
						:name="column.item.name"
						:collapsed="collapsed"
					/>
					<component
						v-else
						:is="column.item.component"
						v-bind="{
							...column.item.props,
							page,
							...(column.collapsible ? { collapsed } : {}),
						}"
					/>
				</template>
			</BodyColumn>

			<ColumnEdge
				v-if="column.edge === 'right'"
				v-bind="edgeProps(column)"
				v-model:dragging="dragging[column.item.name]"
				@toggle="toggle(column)"
				@resize="live[column.item.name] = $event"
				@update:width="settle(column.item.name, $event)"
			/>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import {
	isDrawn,
	projectBody,
	type BodyColumn as Column,
	type BodyItem,
	type RecordPageApi,
} from "@/recordPage";
import BodyColumn from "./BodyColumn.vue";
import ColumnEdge from "./ColumnEdge.vue";
import { useColumnStore } from "./columnStore";

const props = defineProps<{
	items: BodyItem[];
	/** Handed to every script column beside its own props, as a band receives it. */
	page: RecordPageApi;
	user: string;
	/** The row's width in px when the caller knows it; measured from the element otherwise. */
	available?: number;
}>();

const { remembered, remember } = useColumnStore(props.user);
const root = ref<HTMLElement | null>(null);
const measured = ref(0);
const dragging = reactive<Record<string, boolean>>({});
// The width under a drag, drawn at once and stored only when the drag ends.
const live = reactive<Record<string, number>>({});

const columns = computed(() =>
	projectBody(props.items, withLive, props.available ?? measured.value)
);

function withLive(name: string) {
	const width = live[name];
	return width === undefined ? remembered(name) : { ...remembered(name), width };
}

function settle(name: string, width: number) {
	delete live[name];
	remember(name, { width });
}
const drawn = computed(() => columns.value.filter(isDrawn));

function edgeProps(column: Column) {
	return {
		side: column.edge!,
		name: column.item.name,
		open: !column.collapsed,
		width: column.width,
		bounds: column.bounds ?? undefined,
		collapsible: column.collapsible,
	};
}

function toggle(column: Column) {
	remember(column.item.name, { collapsed: !column.collapsed });
}

let observer: ResizeObserver | undefined;

onMounted(() => {
	if (!root.value || typeof ResizeObserver === "undefined") return;
	measured.value = root.value.getBoundingClientRect().width;
	observer = new ResizeObserver(([entry]) => (measured.value = entry.contentRect.width));
	observer.observe(root.value);
});

onBeforeUnmount(() => observer?.disconnect());
</script>
