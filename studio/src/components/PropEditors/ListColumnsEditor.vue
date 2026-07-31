<template>
	<div class="flex w-full flex-col gap-2">
		<ArrayInput
			:modelValue="tracks"
			:label="label"
			addLabel="Add Column"
			newItemValue="8rem"
			emptyMessage="No columns"
			@update:modelValue="setTracks"
			@add="addCells"
			@remove="removeCells"
		/>

		<!-- the tree drifted from `columns` (hand-edited header/rows); ops still apply by position -->
		<div v-if="mismatch.length" class="rounded-sm bg-surface-amber-2 p-2 text-xs text-ink-amber-6">
			{{ mismatch.join(" · ") }}
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import ArrayInput from "@/components/ArrayInput.vue"
import Block from "@/utils/block"
import { listCell, listHeaderCell } from "@/utils/blockTemplate/familyTemplates"

const props = defineProps<{ block: Block; label?: string }>()

// ListHeaderCell and ListHeaderCellSort render the same cell geometry; both count.
const HEADER_CELL_NAMES = ["ListHeaderCell", "ListHeaderCellSort"]

const tracks = computed<string[]>(() => {
	const value = props.block.getProp("columns")
	return Array.isArray(value) ? value : []
})

function setTracks(next: string[]) {
	props.block.setProp("columns", next)
}

// A column lives in three places — a track in `columns`, a header cell, and a cell in
// every row template — kept in step positionally so header and rows never drift.
// ArrayInput edits the tracks; `add`/`remove` mirror the operation onto the cells.
function addCells() {
	headerBlock.value?.addChild(listHeaderCell(`Column ${tracks.value.length}`), null, false)
	rowBlocks.value.forEach((row) => row.addChild(listCell("—"), null, false))
}

function removeCells(index: number) {
	removeCellAt(headerBlock.value, HEADER_CELL_NAMES, index)
	rowBlocks.value.forEach((row) => removeCellAt(row, ["ListCell"], index))
}

const mismatch = computed(() => {
	const expected = tracks.value.length
	const problems: string[] = []
	if (headerBlock.value) {
		const count = cellsOf(headerBlock.value, HEADER_CELL_NAMES).length
		if (count !== expected) problems.push(`Header has ${count} of ${expected} cells`)
	}
	const offRows = rowBlocks.value.filter((row) => cellsOf(row, ["ListCell"]).length !== expected)
	if (offRows.length) {
		problems.push(`${offRows.length} row${offRows.length === 1 ? "" : "s"} with a mismatched cell count`)
	}
	return problems
})

const headerBlock = computed(
	() => props.block.children.find((child) => child.componentName === "ListHeader") || null,
)

// ListRow templates under ListRows — as direct children or slot content, including
// rows nested inside ListGroups.
const rowBlocks = computed(() => {
	const rows: Block[] = []
	const collect = (blocks: Block[]) => {
		blocks.forEach((child) => {
			if (child.componentName === "ListRow") rows.push(child)
			if (child.componentName === "ListGroup") collect(childrenAndSlotContent(child))
		})
	}
	const listRows = props.block.children.find((child) => child.componentName === "ListRows")
	if (listRows) collect(childrenAndSlotContent(listRows))
	return rows
})

// Slot content renders before regular children, so this order matches the visual one.
function childrenAndSlotContent(block: Block): Block[] {
	const slotContent = Object.values(block.componentSlots).flatMap((slot) => slot.slotContent)
	return [...slotContent, ...block.children]
}

function cellsOf(parent: Block, names: string[]): Block[] {
	return childrenAndSlotContent(parent).filter((child) => names.includes(child.componentName))
}

function removeCellAt(parent: Block | null, names: string[], index: number) {
	if (!parent) return
	const cell = cellsOf(parent, names)[index]
	if (cell) parent.removeChild(cell)
}
</script>
