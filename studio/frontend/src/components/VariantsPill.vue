<template>
	<Popover v-if="variantRows.length" v-model:open="open" side="top" align="end" :offset="8" :autoFocus="false">
		<template #trigger>
			<!-- sized exactly like the zoom chip, so the two read as one row of controls -->
			<button
				class="flex cursor-pointer items-center gap-1.5 rounded-6 bg-surface-base px-3 py-2 text-sm text-ink-gray-8 shadow-md"
				@click.stop
			>
				<span class="lucide-split h-4 w-4 text-ink-gray-6" aria-hidden="true" />
				Variants
				<span v-if="anyOffDefault" class="size-1.5 rounded-full bg-surface-blue-7" aria-hidden="true" />
			</button>
		</template>
		<template #default>
			<div class="p-4">
				<VariantRows
					:rows="variantRows"
					canKeep
					selectable
					@pick="pickRow"
					@keep="keepRow"
					@hover="hoverRow"
					@select="selectRow"
				/>
			</div>
		</template>
	</Popover>
	<!-- outline over the hovered row's shown option; fixed and outside any transform,
	     so the measured viewport rect lands where it was measured -->
	<div
		v-if="outlineRect"
		class="pointer-events-none fixed z-50 ring-2 ring-inset ring-outline-blue-4"
		:style="{
			left: `${outlineRect.left}px`,
			top: `${outlineRect.top}px`,
			width: `${outlineRect.width}px`,
			height: `${outlineRect.height}px`,
		}"
		aria-hidden="true"
	/>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue"
import { Popover } from "frappe-ui"
import VariantRows from "@/components/VariantRows.vue"
import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import { confirmKeepVariantOption } from "@/utils/keepVariant"
import {
	getEditorVariantChoice,
	setEditorVariantChoice,
	variantOptionNames,
	type VariantRow,
} from "@/utils/variants"

// The editor's variants pill, beside the zoom chip — the collapsed form the preview
// pill uses, so both surfaces read the same. Rows come from the canvas block tree;
// which option each set shows lives in the editor choice map.
const props = defineProps<{
	// true while the canvas is panned or zoomed: the host hides the pill then, and a
	// panel whose anchor is hidden gets flung to the viewport edge
	suspended?: boolean
}>()

const open = ref(false)
watch(
	() => props.suspended,
	(suspended) => suspended && (open.value = false),
)
// unmounting the panel fires no pointerleave, so clear the outline on any close
watch(open, (isOpen) => !isOpen && outlineVariant(null))

const canvasStore = useCanvasStore()

const variantBlocks = computed(() => collectVariantBlocks(canvasStore.activeCanvas?.getRootBlock()))

function collectVariantBlocks(block?: Block | null): Block[] {
	if (!block) return []
	const found: Block[] = []
	if (block.componentName === "Variants") found.push(block)
	for (const child of block.children || []) found.push(...collectVariantBlocks(child))
	for (const slot of Object.values(block.componentSlots || {})) {
		if (!Array.isArray(slot.slotContent)) continue
		for (const child of slot.slotContent) found.push(...collectVariantBlocks(child as Block))
	}
	return found
}

function shownVariantIndex(variantsBlock: Block) {
	const names = variantOptionNames(variantsBlock)
	return Math.min(getEditorVariantChoice(variantsBlock.componentId), Math.max(names.length - 1, 0))
}

const variantRows = computed<VariantRow[]>(() =>
	variantBlocks.value.map((block) => {
		return {
			key: block.componentId,
			name: block.componentProps.name || "Variant",
			options: variantOptionNames(block),
			activeIndex: shownVariantIndex(block),
		}
	}),
)
const variantBlockOf = (row: VariantRow) => variantBlocks.value.find((block) => block.componentId === row.key)
const anyOffDefault = computed(() => variantRows.value.some((row) => row.activeIndex > 0))

function pickRow(row: VariantRow, option: string) {
	const block = variantBlockOf(row)
	if (!block) return
	const index = variantOptionNames(block).indexOf(option)
	if (index > -1) setEditorVariantChoice(block.componentId, index)
	// re-measure after the swap so the outline hugs the new option
	outlineVariant(block)
}
function keepRow(row: VariantRow) {
	const block = variantBlockOf(row)
	if (!block) return
	outlineVariant(null)
	confirmKeepVariantOption(block, shownVariantIndex(block))
}
function hoverRow(row: VariantRow | null) {
	outlineVariant(row ? (variantBlockOf(row) ?? null) : null)
}
function selectRow(row: VariantRow) {
	variantBlockOf(row)?.selectBlock()
}

// -- outline over the hovered set's shown option, so the row can be spotted on canvas --
const outlineRect = ref<DOMRect | null>(null)

function outlineVariant(variantsBlock: Block | null) {
	if (!variantsBlock) {
		outlineRect.value = null
		return
	}
	nextTick(() => {
		const optionId = variantsBlock.children[shownVariantIndex(variantsBlock)]?.componentId
		const host = optionId
			? document.querySelector(`.__studio_component__[data-component-id="${optionId}"]`)
			: null
		outlineRect.value = host ? host.getBoundingClientRect() : null
	})
}
</script>
