<!--
  The command palette on frappe-ui's `CommandPalette*` parts. It ranks its own rows, so the
  parts' filter is off. The groups and the pinned rows come from `paletteGroups.ts`.
-->
<template>
	<CommandPalette
		v-model:open="paletteOpen"
		v-model:query="query"
		:filterable="false"
		:title="__('Search and run')"
		@select="select"
	>
		<CommandPaletteInput :placeholder="__('Search or run an action')" />

		<CommandPaletteList>
			<CommandPaletteGroup v-for="group in groups" :key="group.label" :label="group.label">
				<PaletteRow v-for="row in group.rows" :key="row.id" :row="row" />
			</CommandPaletteGroup>
		</CommandPaletteList>

		<!-- A second listbox, so the arrow keys reach these rows and they never scroll away. -->
		<CommandPaletteList
			v-if="pinned.length"
			data-slot="palette-pinned"
			class="shrink-0 border-t border-outline-gray-1 py-2 dark:border-outline-gray-2"
		>
			<PaletteRow v-for="row in pinned" :key="row.id" :row="row" />
		</CommandPaletteList>

		<CommandPaletteEmpty v-slot="{ query: text }">
			{{ text.trim() ? __("No results for “{0}”", [text.trim()]) : __("Type to search") }}
		</CommandPaletteEmpty>

		<CommandPaletteFooter>
			<span class="flex items-center gap-1.5">
				<KeyboardShortcut combo="ArrowUp" bg class="[&_kbd]:leading-none" />
				<KeyboardShortcut combo="ArrowDown" bg class="[&_kbd]:leading-none" />
				{{ __("to move") }}
			</span>
			<span class="flex items-center gap-1.5">
				<KeyboardShortcut combo="Enter" bg class="[&_kbd]:leading-none" />
				{{ __("to run") }}
			</span>
			<span class="ml-auto flex items-center gap-1.5">
				<KeyboardShortcut combo="Escape" bg class="[&_kbd]:leading-none" />
				{{ __("to close") }}
			</span>
		</CommandPaletteFooter>
	</CommandPalette>
</template>

<script setup lang="ts">
import { computed, inject, ref } from "vue";
import { useRouter } from "vue-router";
import { KeyboardShortcut } from "frappe-ui";
import {
	CommandPalette,
	CommandPaletteEmpty,
	CommandPaletteFooter,
	CommandPaletteGroup,
	CommandPaletteInput,
	CommandPaletteList,
} from "frappe-ui/experimental";
import type { Boot } from "@/boot";
import { paletteOpen, type PaletteRow as Row } from "./palette";
import { paletteGroups, pinnedRows, type PaletteContext } from "./paletteGroups";
import PaletteRow from "./PaletteRow.vue";

const context: PaletteContext = { boot: inject<Boot>("boot")!, router: useRouter() };
const query = ref("");

const groups = computed(() =>
	paletteGroups
		.map((group) => ({ label: group.label, rows: group.rows(query.value, context) }))
		.filter((group) => group.rows.length)
);

const pinned = computed(() => pinnedRows.flatMap((rows) => rows(query.value, context)));

function select(value: unknown) {
	(value as Row).run();
}
</script>
