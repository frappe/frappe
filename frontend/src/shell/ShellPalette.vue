<!--
  The command palette on frappe-ui's `CommandPalette*` parts. It ranks its own rows, so the
  parts' filter is off. The groups and the pinned rows come from `PaletteSearch`, which the
  index's filter box draws from too.
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
				:placeholder="step?.placeholder ?? __('Search or run an action')"
				@keydown="(event: KeyboardEvent) => onKeydown(event, active as Row | undefined)"
			>
				<template v-if="step" #prefix>
					<span
						data-slot="palette-chip"
						class="inline-flex h-6 shrink-0 items-center gap-1.5 rounded-4 bg-surface-gray-3 pl-2 pr-1 text-sm text-ink-gray-8"
					>
						<span
							:class="[step.icon, 'size-3.5 text-ink-gray-6']"
							aria-hidden="true"
						/>
						{{ step.chip }}
						<button
							type="button"
							class="flex size-4 items-center justify-center rounded-2 text-ink-gray-5 hover:bg-surface-gray-4 hover:text-ink-gray-8"
							tabindex="-1"
							:aria-label="__('Back')"
							@mousedown.prevent
							@click="step.leave()"
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
					step?.prompt ??
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
					{{ step ? __("back") : __("to close") }}
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
	type CommandPaletteSelectEvent,
} from "frappe-ui/experimental";
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { paletteOpen, type PaletteRow as Row } from "./palette";
import { usePaletteArgument } from "./paletteArgument";
import { PaletteSearch, type PaletteContext } from "./paletteGroups";
import { usePaletteScope } from "./paletteScope";
import { PaletteHighlight } from "./paletteHighlight";
import PaletteRow from "./PaletteRow.vue";

const context: PaletteContext = {
	boot: inject<Boot>("boot")!,
	router: useRouter(),
	addresses: inject<Addresses>("addresses")!,
};
const search = new PaletteSearch(context);
const query = ref("");
const scope = usePaletteScope(query, context);
const argument = usePaletteArgument(query);

/** The palette's second step, if it is in one: an act's argument, or a doctype Tab narrowed to. */
const step = computed(() => {
	const act = argument.act.value;
	if (act?.argument)
		return {
			chip: act.label ?? act.name,
			icon: act.icon ?? "lucide-chevron-right",
			placeholder: __("Search {0}", [act.argument.label]),
			heading: act.argument.label,
			rows: argument.rows.value,
			prompt: argument.prompt.value,
			leave: argument.leave,
		};
	const doctype = scope.doctype.value;
	if (doctype)
		return {
			chip: __("in {0}", [__(doctype)]),
			icon: "lucide-list",
			placeholder: __("Search {0}", [__(doctype)]),
			heading: __("Records"),
			rows: scope.rows.value,
			prompt: scope.prompt.value,
			leave: scope.leave,
		};
	return null;
});

// A closed palette, or one in a second step, asks nothing more of the groups' server searches.
watch(
	[query, () => context.router.currentRoute.value.path, () => Boolean(step.value), paletteOpen],
	([text, , stepped, isOpen]) => search.follow(isOpen && !stepped ? text : "")
);

// The scope is left on the next open, so the closing palette keeps its rows as it fades.
watch(
	paletteOpen,
	(isOpen) => {
		if (!isOpen) return;
		scope.leave();
		search.load();
	},
	{ immediate: true }
);

const groups = computed(() => {
	if (step.value)
		return step.value.rows.length
			? [{ label: step.value.heading, rows: step.value.rows }]
			: [];
	return search.groups(query.value);
});

// A second step pins nothing, so its own prompts stay in view.
const pinned = computed(() => (step.value ? [] : search.pinned(query.value)));

const drawnRows = computed(() => [
	...groups.value.flatMap((group) => group.rows),
	...pinned.value,
]);

function select(value: unknown, event: CommandPaletteSelectEvent) {
	const row = value as Row;
	if (row.stays) event.preventDefault();
	row.run();
}

function narrowable(row: Row | undefined): row is Row & { doctype: string } {
	return !step.value && !!row?.doctype;
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
	if (back && step.value) {
		event.preventDefault();
		event.stopPropagation();
		step.value.leave();
	}
}
</script>
