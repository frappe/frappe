<!-- The palette's rows for what the box holds, under the tiles: one list per group, Ask Flow last. -->
<template>
	<div class="mt-10 flex w-full flex-col gap-6" data-index-results>
		<section v-for="(group, position) in drawn" :key="group.label || 'pinned'">
			<h2
				v-if="group.label"
				:id="`${idPrefix}-${position}-title`"
				class="mb-2 text-sm font-medium text-ink-gray-5"
			>
				{{ group.label }}
			</h2>
			<!-- Out by the row's own padding, so a row's icon and hint sit on the box's edges. -->
			<ul
				:id="`${idPrefix}-${position}`"
				role="listbox"
				:aria-labelledby="group.label ? `${idPrefix}-${position}-title` : undefined"
				:aria-label="group.label ? undefined : group.rows[0]?.lead"
				class="-mx-3 flex flex-col"
			>
				<li v-for="row in group.rows" :key="row.row.id" role="none">
					<ItemListRow
						:id="selection.idOf(row.key)"
						:as="row.row.href ? 'a' : 'button'"
						size="lg"
						:href="row.row.href"
						:type="row.row.href ? undefined : 'button'"
						role="option"
						tabindex="-1"
						:aria-selected="row.selected"
						:aria-disabled="!row.pickable || undefined"
						:disabled="!row.pickable"
						class="text-left outline-none focus-visible:focus-ring"
						:class="{
							'hover:bg-surface-gray-2': row.pickable,
							'bg-surface-gray-2': row.selected,
						}"
						:data-result="row.row.id"
						:data-selected="row.selected || undefined"
						@click="pick(row.row, $event)"
					>
						<template #prefix>
							<LoadingIndicator
								v-if="row.row.pending"
								class="size-4 shrink-0 text-ink-gray-5"
							/>
							<span
								v-else
								:class="[row.row.icon, 'size-4 shrink-0 text-ink-gray-6']"
								aria-hidden="true"
							/>
						</template>
						<span class="flex min-w-0 items-baseline gap-2" :title="row.text">
							<span class="truncate text-ink-gray-8">
								<span v-if="row.row.lead" class="text-ink-gray-6">{{
									row.row.lead
								}}</span>
								{{ row.row.label }}
							</span>
							<span
								v-if="row.row.description"
								class="max-w-[45%] shrink-0 truncate text-sm text-ink-gray-5"
							>
								{{ row.row.description }}
							</span>
						</span>
						<template v-if="row.row.key" #suffix>
							<!-- A flex box and its own `leading-none`, or the key's line makes the row taller. -->
							<span class="flex">
								<KeyboardShortcut :combo="row.row.key" class="leading-none" />
							</span>
						</template>
						<template v-else-if="row.row.hint" #suffix>
							<span class="text-sm text-ink-gray-5">{{ row.row.hint }}</span>
						</template>
					</ItemListRow>
				</li>
			</ul>
		</section>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { ItemListRow, KeyboardShortcut, LoadingIndicator } from "frappe-ui";
import type { PaletteRow } from "@/shell/palette";
import type { DrawnGroup } from "@/shell/paletteGroups";
import { pickable, resultKey } from "./indexSearch";
import type { Selection } from "./selection";

const props = defineProps<{ idPrefix: string; groups: DrawnGroup[]; selection: Selection }>();

const drawn = computed(() =>
	props.groups.map((group) => ({
		label: group.label,
		rows: group.rows.map((row) => {
			const key = resultKey(row);
			return {
				row,
				key,
				pickable: pickable(row),
				selected: props.selection.isSelected(key),
				text: [row.lead, row.label, row.description].filter(Boolean).join(" "),
			};
		}),
	}))
);

// A link opens by itself, so Mod-click still opens a new tab.
function pick(row: PaletteRow, event: MouseEvent) {
	if (row.href || !pickable(row)) return;
	event.preventDefault();
	row.run();
}
</script>
