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
		<template #default="{ active }">
			<CommandPaletteInput
				:placeholder="
					scope.doctype.value
						? __('Search {0}', [__(scope.doctype.value)])
						: __('Search or run an action')
				"
				@keydown="(event: KeyboardEvent) => onKeydown(event, active as Row | undefined)"
			>
				<template v-if="scope.doctype.value" #prefix>
					<span
						data-slot="palette-scope-chip"
						class="inline-flex h-6 shrink-0 items-center gap-1.5 rounded-4 bg-surface-gray-3 pl-2 pr-1 text-sm text-ink-gray-8"
					>
						<span class="lucide-list size-3.5 text-ink-gray-6" aria-hidden="true" />
						{{ __("in {0}", [__(scope.doctype.value)]) }}
						<button
							type="button"
							class="flex size-4 items-center justify-center rounded-2 text-ink-gray-5 hover:bg-surface-gray-4 hover:text-ink-gray-8"
							tabindex="-1"
							:aria-label="__('Back')"
							@click="scope.leave()"
						>
							<span class="lucide-x size-3" aria-hidden="true" />
						</button>
					</span>
				</template>
			</CommandPaletteInput>

			<!-- One listbox: reka orders the rows of a second one by when they mounted, not by place. -->
			<CommandPaletteList class="flex flex-col">
				<div role="none" tabindex="-1" class="min-h-0 overflow-y-auto overscroll-contain">
					<CommandPaletteGroup
						v-for="group in groups"
						:key="group.label"
						:label="group.label"
					>
						<PaletteRow v-for="row in group.rows" :key="row.id" :row="row" />
					</CommandPaletteGroup>
				</div>
				<!-- Alone, it draws no rule of its own: the input's already sits above it. -->
				<div
					v-if="pinned.length"
					role="none"
					data-slot="palette-pinned"
					class="shrink-0 border-outline-gray-1 py-2 dark:border-outline-gray-2"
					:class="{ 'border-t': groups.length }"
				>
					<PaletteRow v-for="row in pinned" :key="row.id" :row="row" />
				</div>
			</CommandPaletteList>
			<PaletteHighlight :rows="drawnRows" />

			<CommandPaletteEmpty v-slot="{ query: text }">
				{{
					scope.prompt.value ??
					(text.trim()
						? __("No results for “{0}”", [text.trim()])
						: __("Type to search"))
				}}
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
				<span
					v-if="narrowable(active as Row | undefined)"
					data-slot="palette-tab-hint"
					class="flex items-center gap-1.5"
				>
					<KeyboardShortcut combo="Tab" bg class="[&_kbd]:leading-none" />
					{{ __("to search in {0}", [__((active as Row).doctype!)]) }}
				</span>
				<span class="ml-auto flex items-center gap-1.5">
					<KeyboardShortcut combo="Escape" bg class="[&_kbd]:leading-none" />
					{{ scope.doctype.value ? __("back") : __("to close") }}
				</span>
			</CommandPaletteFooter>
		</template>
	</CommandPalette>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from "vue";
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
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { paletteOpen, type PaletteRow as Row } from "./palette";
import { paletteGroups, pinnedRows, type PaletteContext } from "./paletteGroups";
import { loadPlaces } from "./palettePlaces";
import { usePaletteScope } from "./paletteScope";
import { PaletteHighlight } from "./paletteHighlight";
import PaletteRow from "./PaletteRow.vue";

const context: PaletteContext = {
	boot: inject<Boot>("boot")!,
	router: useRouter(),
	addresses: inject<Addresses>("addresses")!,
};
const query = ref("");
const scope = usePaletteScope(query, context);

// A closed or narrowed palette asks nothing more of the groups' server searches.
watch(
	[query, () => context.router.currentRoute.value.path, scope.doctype, paletteOpen],
	([text, , narrowed, isOpen]) => {
		const asked = isOpen && !narrowed ? text : "";
		paletteGroups.forEach((group) => group.follow?.(asked, context));
	}
);

// The scope is left on the next open, so the closing palette keeps its rows as it fades.
watch(
	paletteOpen,
	(isOpen) => {
		if (!isOpen) return;
		scope.leave();
		loadPlaces(context.boot);
	},
	{ immediate: true }
);

const groups = computed(() => {
	if (scope.doctype.value)
		return scope.rows.value.length ? [{ label: __("Records"), rows: scope.rows.value }] : [];
	return paletteGroups
		.map((group) => ({ label: group.label, rows: group.rows(query.value, context) }))
		.filter((group) => group.rows.length);
});

// A narrowed palette pins nothing, so its own prompts stay in view.
const pinned = computed(() =>
	scope.doctype.value ? [] : pinnedRows.flatMap((rows) => rows(query.value, context))
);

const drawnRows = computed(() => [
	...groups.value.flatMap((group) => group.rows),
	...pinned.value,
]);

function select(value: unknown) {
	(value as Row).run();
}

function narrowable(row: Row | undefined): row is Row & { doctype: string } {
	return !scope.doctype.value && !!row?.doctype;
}

// Tab, Esc and Backspace are stopped here, or the dialog moves the focus out or closes.
function onKeydown(event: KeyboardEvent, active: Row | undefined) {
	if (event.isComposing) return;
	if (event.key === "Tab" && !event.shiftKey && narrowable(active)) {
		event.preventDefault();
		event.stopPropagation();
		scope.enter(active.doctype);
		return;
	}
	const back = event.key === "Escape" || (event.key === "Backspace" && !query.value);
	if (back && scope.doctype.value) {
		event.preventDefault();
		event.stopPropagation();
		scope.leave();
	}
}
</script>
