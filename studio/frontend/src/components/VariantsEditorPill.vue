<template>
	<Popover v-if="variantRows.length" v-model:open="open" side="top" align="end" :offset="8" :autoFocus="false">
		<template #trigger>
			<!-- sized like the zoom chip, so the two look like one row of controls -->
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
	<BlockOutline :rect="outlineRect" />
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { call, dialog, Popover } from "frappe-ui"
import BlockOutline from "@/components/BlockOutline.vue"
import VariantRows from "@/components/VariantRows.vue"
import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import useComponentStore from "@/stores/componentStore"
import useStudioStore from "@/stores/studioStore"
import { useBlockOutline } from "@/utils/useBlockOutline"
import {
	getEditorVariantChoice,
	keepDialogText,
	setEditorVariantChoice,
	variantOptionNames,
	type VariantRow,
} from "@/utils/variants"
import { confirmKeepVariantOption } from "@/utils/variantsEditor"

// The editor's variants pill, beside the zoom chip. It uses the collapsed form of the live
// app's pill, so both look the same. Rows come from the canvas block tree, and the option each
// set shows comes from the editor choice map.
const props = defineProps<{
	// true while the canvas is panned or zoomed. The host hides the pill then, and a panel
	// with a hidden anchor jumps to the edge of the viewport.
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
const componentStore = useComponentStore()
const componentEditorStore = useComponentEditorStore()
const store = useStudioStore()

// A set can live in the page tree, or in a studio component the page uses. A component's set
// is listed once, however many instances render it. One choice drives them all, because the
// instances share the definition's block ids.
interface VariantSource {
	block: Block
	ownerComponent?: string
}

const variantSources = computed<VariantSource[]>(() => {
	const sources: VariantSource[] = []
	const visitedComponents = new Set<string>()

	function collect(block?: Block | null, ownerComponent?: string) {
		if (!block) return
		const isVariantSet = block.componentName === "Variants"
		if (isVariantSet) sources.push({ block, ownerComponent })
		if (block.isStudioComponent && !visitedComponents.has(block.componentName)) {
			visitedComponents.add(block.componentName)
			collect(componentStore.componentMap.get(block.componentName), block.componentName)
		}
		// the options a set hides are not on the canvas, so a set inside one is not listed
		const children = block.children || []
		for (const child of isVariantSet ? [children[shownVariantIndex(block)]] : children) {
			collect(child, ownerComponent)
		}
		for (const slot of Object.values(block.componentSlots || {})) {
			if (!Array.isArray(slot.slotContent)) continue
			for (const child of slot.slotContent) collect(child as Block, ownerComponent)
		}
	}

	collect(canvasStore.activeCanvas?.getRootBlock())
	return sources
})

const variantBlocks = computed(() => variantSources.value.map((source) => source.block))

function shownVariantIndex(variantsBlock: Block) {
	return getEditorVariantChoice(variantsBlock.componentId, variantsBlock.children.length)
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
const variantSourceOf = (row: VariantRow) =>
	variantSources.value.find((source) => source.block.componentId === row.key)
const variantBlockOf = (row: VariantRow) => variantSourceOf(row)?.block
const anyOffDefault = computed(() => variantRows.value.some((row) => row.activeIndex > 0))

function pickRow(row: VariantRow, option: string) {
	const block = variantBlockOf(row)
	if (!block) return
	const index = variantOptionNames(block).indexOf(option)
	if (index > -1) setEditorVariantChoice(block.componentId, index)
	// measure again after the swap, so the outline fits the new option
	outlineVariant(block)
}
function keepRow(row: VariantRow) {
	const source = variantSourceOf(row)
	if (!source) return
	outlineVariant(null)
	if (!source.ownerComponent) {
		confirmKeepVariantOption(source.block, shownVariantIndex(source.block))
		return
	}
	// the set lives in a studio component, so Keep edits the component. It is saved on the
	// server, every instance on every page follows it, and the page cannot undo it
	const ownerComponent = source.ownerComponent
	dialog.confirm({
		...keepDialogText(row.options, shownVariantIndex(source.block)),
		confirmLabel: "Keep",
		onConfirm: async () => {
			await call("frappe.studio.doctype.studio_page.studio_page.keep_variant", {
				app_name: store.activeApp?.name,
				page_name: store.activePage?.name,
				block_id: source.block.componentId,
				option_name: row.options[shownVariantIndex(source.block)],
			})
			await componentStore.reloadComponent(ownerComponent)
		},
	})
}
function hoverRow(row: VariantRow | null) {
	outlineVariant(row ? (variantBlockOf(row) ?? null) : null)
}
function selectRow(row: VariantRow) {
	const source = variantSourceOf(row)
	if (!source) return
	// a component's blocks cannot be selected on the page canvas, so open the component
	if (source.ownerComponent) componentEditorStore.editComponent(source.ownerComponent)
	else source.block.selectBlock()
}

const { rect: outlineRect, outline } = useBlockOutline()

function outlineVariant(variantsBlock: Block | null) {
	const shownOption = () => variantsBlock?.children[shownVariantIndex(variantsBlock)] ?? null
	outline(variantsBlock ? () => shownOption()?.getRenderedElement() ?? null : null)
}
</script>
