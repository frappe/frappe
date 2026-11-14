<!-- The left pane's listbox: Up and Down select, Alt+Up and Alt+Down move, Enter opens the form. -->
<template>
	<ul
		v-if="list.length"
		role="listbox"
		:aria-label="__('Rows')"
		class="flex flex-col gap-0.5"
		data-editor-list
		@keydown="onKey"
	>
		<li
			v-for="({ row, depth }, at) in list"
			:id="`editor-row-${row.key}`"
			:key="row.key"
			role="option"
			:aria-selected="row.key === selected"
			:tabindex="row.key === active ? 0 : -1"
			:data-key="row.key"
			draggable="true"
			:class="[
				'group/row flex h-7 cursor-pointer items-center rounded-4 px-2 text-sm outline-none transition focus-visible:focus-ring',
				row.key === selected
					? 'bg-surface-elevation-3 text-ink-gray-8 shadow-sm'
					: 'text-ink-gray-7 hover:bg-surface-gray-2',
			]"
			@click="emit('select', row.key)"
			@dragstart="dragged = row.key"
			@dragover.prevent
			@drop.prevent="drop(row.key)"
		>
			<span
				v-for="guide in depth"
				:key="guide"
				class="flex h-full w-4 shrink-0 justify-center"
			>
				<span class="h-full border-l border-outline-gray-2" />
			</span>
			<Icon
				:name="iconFor(row)"
				:class="['shrink-0', row.hidden ? 'text-ink-gray-5' : 'text-ink-gray-6']"
			/>
			<span
				:title="titleFor(row)"
				:class="[
					'ml-2 min-w-0 flex-1 truncate',
					row.hidden ? 'text-ink-gray-6' : '',
					row.item_type === 'Section' ? 'font-medium text-ink-gray-8' : '',
				]"
			>
				{{ titleFor(row) }}
			</span>
			<Badge
				v-if="badge(row)"
				:label="badge(row)!.label"
				:theme="badge(row)!.theme"
				size="sm"
				class="ml-2 shrink-0"
			/>
			<span
				class="lucide-grip-vertical ml-1 size-3.5 shrink-0 cursor-grab text-ink-gray-4 opacity-0 group-hover/row:opacity-100"
			/>
		</li>
	</ul>
	<p v-else class="px-2 py-1 text-sm text-ink-gray-5">{{ __("Nothing here yet.") }}</p>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Badge } from "frappe-ui";
import { __ } from "@/i18n";
import Icon from "@/icons/Icon.vue";
import { acts } from "@/acts/dispatcher";
import { type EditorRow, isOwn, type Scope } from "./draft";

const props = defineProps<{
	rows: EditorRow[];
	showHidden: boolean;
	selected: string | null;
	scope: Scope;
	iconFor: (row: EditorRow) => string;
	titleFor: (row: EditorRow) => string;
}>();
const emit = defineEmits<{
	select: [key: string];
	move: [key: string, by: 1 | -1];
	dropBefore: [key: string, before: string];
	open: [key: string];
}>();

const dragged = ref<string | null>(null);

const list = computed(() => {
	const shown = props.rows.filter((row) => props.showHidden || !row.hidden);
	const byKey = new Map(shown.map((row) => [row.key, row]));
	// One guide per level of the parent chain that is on show, as far as the depth cap allows.
	const depth = (row: EditorRow) => {
		let levels = 0;
		for (
			let up = byKey.get(row.parent_key ?? "");
			up && levels < shown.length;
			up = byKey.get(up.parent_key ?? "")
		) {
			levels++;
		}
		return levels;
	};
	return shown.map((row) => ({ row, depth: depth(row) }));
});

/** The row that takes the keyboard: the selected one, or the first when that one is not listed. */
const active = computed(() => {
	const listed = (key: string | null) => list.value.some(({ row }) => row.key === key);
	return listed(props.selected) ? props.selected : list.value[0]?.row.key;
});

/** An Act row draws when the act is present, or is an app's whose acts are still loading (as the sidebar row decides). */
function actAvailable(name: string): boolean {
	return !!acts.find(name) || acts.loads(name);
}

type Badged = { label: string; theme: "gray" | "red" };

/** One state per row, the heaviest first. */
function badge(row: EditorRow): Badged | null {
	if (row.no_access) return { label: __("No access"), theme: "red" };
	if (row.view_deleted) return { label: __("View deleted"), theme: "red" };
	if (row.item_type === "Act" && !actAvailable(String(row.payload?.act ?? "")))
		return { label: __("Not available"), theme: "red" };
	if (row.hidden && row.hidden_by === "site" && props.scope === "user")
		return { label: __("Hidden for everyone"), theme: "gray" };
	if (row.hidden) return { label: __("Hidden"), theme: "gray" };
	if (isOwn(row.key, props.scope)) return { label: __("Added"), theme: "gray" };
	return null;
}

function drop(before: string) {
	if (dragged.value && dragged.value !== before) emit("dropBefore", dragged.value, before);
	dragged.value = null;
}

function onKey(event: KeyboardEvent) {
	if (event.key === "Enter") {
		const focused = (event.target as HTMLElement).dataset.key;
		if (!focused) return;
		event.preventDefault();
		return emit("open", focused);
	}
	const by = event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0;
	const at = list.value.findIndex(({ row }) => row.key === active.value);
	if (!by || at < 0) return;
	event.preventDefault();

	const key = list.value[at].row.key;
	if (event.altKey) return emit("move", key, by);

	const next = list.value[at + by];
	if (!next) return;
	emit("select", next.row.key);
	requestAnimationFrame(() => document.getElementById(`editor-row-${next.row.key}`)?.focus());
}
</script>
