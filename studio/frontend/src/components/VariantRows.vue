<template>
	<DefineRow v-slot="{ row, soloRow }">
		<!-- In the grid each row is a subgrid, so names, options and Keep line up across rows. -->
		<div
			class="items-center"
			:class="soloRow ? 'flex gap-2' : 'col-span-full grid grid-cols-subgrid'"
			@mouseenter="emit('hover', row)"
			@mouseleave="emit('hover', null)"
		>
			<!-- a literal <button>: a string :is resolves to the globally registered frappe-ui Button -->
			<button
				v-if="selectable"
				class="min-w-0 justify-self-start truncate text-p-sm text-ink-gray-8 hover:text-ink-gray-9"
				title="Select the variants block"
				@click="emit('select', row)"
			>
				{{ row.name }}
			</button>
			<span v-else class="min-w-0 truncate text-p-sm" :class="soloRow ? 'text-ink-gray-5' : 'text-ink-gray-8'">
				{{ row.name }}
			</span>
			<TabButtons
				class="justify-self-end"
				:options="row.options.map((option) => ({ value: option, label: option }))"
				:model-value="row.options[row.activeIndex]"
				@update:model-value="(value: string | number) => emit('pick', row, String(value))"
			/>
			<template v-if="canKeep">
				<span class="flex shrink-0 justify-end">
					<button
						class="text-p-sm text-ink-gray-5 hover:text-ink-gray-8"
						title="Keep the shown option and delete the others"
						:aria-label="`Keep ${row.options[row.activeIndex]} for ${row.name}`"
						@click="emit('keep', row)"
					>
						Keep
					</button>
				</span>
			</template>
		</div>
	</DefineRow>

	<Row v-if="solo && rows[0]" :row="rows[0]" soloRow />
	<div
		v-else
		class="grid items-center gap-x-4 gap-y-3"
		:class="canKeep ? 'grid-cols-[auto_auto_auto]' : 'grid-cols-[auto_auto]'"
	>
		<Row v-for="row in rows" :key="row.key" :row="row" />
	</div>
</template>

<script setup lang="ts">
import { createReusableTemplate } from "@vueuse/core"
import { TabButtons } from "frappe-ui"
import type { VariantRow } from "@/utils/variants"

// The switcher rows both pills share: name · options · Keep. Purely visual —
// each pill wires the emits to its own state.
defineProps<{
	rows: VariantRow[]
	canKeep?: boolean
	// render only the first row, inline — the viewer pill's single-set mode
	solo?: boolean
	// the editor's rows: clicking a name selects the Variants block
	selectable?: boolean
}>()

const emit = defineEmits<{
	pick: [row: VariantRow, option: string]
	keep: [row: VariantRow]
	hover: [row: VariantRow | null]
	select: [row: VariantRow]
}>()

const [DefineRow, Row] = createReusableTemplate<{ row: VariantRow; soloRow?: boolean }>({
	inheritAttrs: false,
	// Declared, so a bare `soloRow` arrives as true rather than as an empty attribute.
	props: { row: { type: Object, required: true }, soloRow: Boolean },
})
</script>
