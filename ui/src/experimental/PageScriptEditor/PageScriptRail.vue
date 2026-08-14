<template>
	<div class="flex w-64 shrink-0 flex-col border-r border-outline-gray-1 p-4">
		<!-- Flush at the panel's left padding — the same x as the header's title
		     and the rows' own left edge (ticket 37, amendment 2). An earlier pass
		     aligned this to the grip's *ink* instead: lucide's `grip-vertical`
		     draws its dots 4px into its box, so the boxes agreed while the dots
		     did not. Aligning to the column is what makes the rail read as one
		     column under the header rather than a heading hung off the rows.

		     The rail is labelled, not explained (ticket 23): four words and an
		     arrow replace two lines of prose, and only once there is an order to
		     describe — a list of one runs in no particular order. -->
		<div v-if="scripts.length > 1" class="flex items-center gap-1 pb-2">
			<span class="text-p-xs text-ink-gray-5">Runs in this order</span>
			<span class="text-p-xs text-ink-gray-4">↓</span>
		</div>

		<!-- The gutter is negative margin plus equal padding, so nothing moves:
		     `overflow-y-auto` clips on *both* axes, and a selected `SidebarItem`
		     is raised (`shadow-sm`), so without it the shadow is sliced flat at
		     all four edges of the list — top and bottom included (ticket 37).

		     Dragging is the only way to change run order, so it is gated on there
		     being an order to change: with one script the grip is absent and the
		     list is inert. `handle` keeps the whole row clickable — only the grip
		     starts a drag, so a click still selects. `#item` must hold exactly one
		     node, comments included, or vuedraggable throws. -->
		<Draggable
			class="-m-1 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-1"
			tag="div"
			:modelValue="scripts"
			:itemKey="(row: PageScriptDoc) => row.name"
			:disabled="!reorderable"
			handle=".page-script-drag-handle"
			@update:modelValue="dropped"
		>
			<template #item="{ element: row }">
				<SidebarItem
					:active="row.name === selectedName"
					:aria-current="row.name === selectedName"
					class="group/row cursor-pointer"
					@click="emit('select', row.name)"
				>
					<template #prefix>
						<span
							v-if="reorderable"
							class="page-script-drag-handle lucide-grip-vertical size-3 shrink-0 cursor-grab text-ink-gray-3 transition-colors group-hover/row:text-ink-gray-5"
							aria-hidden="true"
						/>
					</template>

					<span class="flex min-w-0 items-center">
						<!-- No unsaved dot here: the header's `Unsaved` badge already
						     says the editor holds an unsaved script, and saying it twice
						     on one screen is what 23's footer line did. This **amends
						     37**, whose item 4 gave the row a mark of its own so the
						     rail could say *which* scripts are dirty — the trade is that
						     with a buffer per script, several can be dirty at once and
						     only the open one now shows it. Accepted: the rail is a list
						     of scripts, not a list of edits. -->
						<!-- Disabled-ness is carried by the dimmed label alone — no `Off`
						     badge (amends 23). That leaves the suffix to the `⋯`, which
						     is also the only place Enable/Disable lives, so the state and
						     the way to change it are one hop apart. The row is not
						     numbered either: position plus the rail's label already say
						     the order, and the number said it a third time. -->
						<span
							class="block min-w-0 truncate text-p-sm"
							:class="row.enabled ? 'text-ink-gray-8' : 'text-ink-gray-4'"
						>
							{{ row.name }}
						</span>
					</span>

					<!-- `SidebarItem`'s suffix zone is a *sibling* of the row's button
					     rather than a child, which is what makes the `⋯` legal HTML:
					     today's `ItemListRow as="button"` nests one interactive element
					     inside another, so the menu sat inside the row's own button
					     (ticket 37, item 2 — measured 1 nested element per row, now 0).

					     2px, matching the 2px the 24px `xs` button already has above and
					     below it inside a 28px row, so the `⋯` is inset evenly on all
					     four sides. -->
					<template #suffix>
						<span class="mr-0.5 flex items-center">
							<Dropdown :options="options(row)" align="end">
								<Button
									variant="ghost"
									size="xs"
									icon="lucide-ellipsis"
									:label="`Actions for ${row.name}`"
									class="shrink-0"
									:class="
										row.name === selectedName
											? ''
											: 'opacity-0 group-hover/row:opacity-100'
									"
								/>
							</Dropdown>
						</span>
					</template>
				</SidebarItem>
			</template>
		</Draggable>

		<Button
			class="mt-2"
			iconLeft="lucide-plus"
			label="New script"
			:disabled="busy"
			@click="emit('create')"
		/>
	</div>
</template>

<script setup lang="ts">
// The script list: selection, run position, and every per-script action. The
// destructive ones live here rather than beside Save, so nothing routine sits
// next to them (ticket 23).
//
// The row is frappe-ui's `SidebarItem` — the same primitive the app's own left
// nav draws with (ticket 37 item 2, which amends 23's `ItemListRow`).
import { computed } from "vue";
import { Button, Dropdown, SidebarItem } from "frappe-ui";
// @ts-ignore — vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import { rowActions } from "./rowActions";
import type { PageScriptDoc } from "./pageScriptApi";

const props = defineProps<{
	scripts: PageScriptDoc[];
	selectedName: string | null;
	/** A write is in flight; the list stays readable but adds nothing new. */
	busy?: boolean;
}>();

const emit = defineEmits<{
	select: [name: string];
	create: [];
	toggleEnabled: [row: PageScriptDoc];
	duplicate: [row: PageScriptDoc];
	remove: [row: PageScriptDoc];
	/** The whole list in its new order — order belongs to the list, not a row. */
	reorder: [names: string[]];
}>();

const reorderable = computed(() => props.scripts.length > 1);

// The rail owns no state, so it reports the dropped order rather than applying
// it: the pane holds the list, and it is the pane's write that has to be able
// to put it back if the server refuses.
function dropped(rows: PageScriptDoc[]) {
	emit(
		"reorder",
		rows.map((row) => row.name),
	);
}

function options(row: PageScriptDoc) {
	return rowActions(
		row,
		{
			toggleEnabled: (target) => emit("toggleEnabled", target),
			duplicate: (target) => emit("duplicate", target),
			remove: (target) => emit("remove", target),
		},
		props.busy,
	);
}
</script>
