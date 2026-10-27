<template>
	<div class="flex w-full flex-col gap-1.5">
		<InputLabel v-if="label" class="mb-1">{{ label }} · {{ options.length }}</InputLabel>

		<RadioGroup
			size="sm"
			:modelValue="String(shownIndex)"
			@update:modelValue="(value: any) => showOption(Number(value))"
		>
			<div class="flex flex-col divide-y divide-outline-gray-1 overflow-hidden rounded-4 border border-outline-gray-1">
				<div
					v-for="(option, index) in options"
					:key="index"
					class="flex items-center gap-2 px-2.5 py-2"
					:class="{ 'opacity-50': dragIndex === index }"
					:draggable="dragHandleIndex === index"
					@dragstart="onDragStart(index, $event)"
					@dragend="resetDrag"
					@dragover.prevent
					@drop.prevent="onDrop(index)"
				>
					<button
						class="flex-none cursor-grab text-ink-gray-4 hover:text-ink-gray-7"
						title="Drag to reorder"
						tabindex="-1"
						@mousedown="dragHandleIndex = index"
						@mouseup="resetDrag"
					>
						<LucideGripVertical class="size-3" />
					</button>
					<Radio :value="String(index)" :title="`Show ${option || `Option ${index + 1}`} on the canvas`" />
					<Input
						v-if="renamingIndex === index"
						:ref="focusRenameInput"
						class="min-w-0 flex-1"
						hideClearButton
						:modelValue="option"
						@blur="(event: FocusEvent) => commitRename(index, (event.target as HTMLInputElement).value)"
						@keydown.enter="(event: KeyboardEvent) => (event.target as HTMLInputElement).blur()"
						@keydown.esc="renamingIndex = null"
					/>
					<span
						v-else
						class="min-w-0 flex-1 cursor-default truncate text-p-sm text-ink-gray-7"
						@dblclick="startRename(index)"
					>
						{{ option || `Option ${index + 1}` }}
					</span>
					<Dropdown :options="rowMenu(index)">
						<template v-slot="{ open }">
							<button
								class="flex cursor-pointer items-center rounded-1 p-1 text-ink-gray-6 hover:bg-surface-gray-4"
								:class="open ? 'bg-surface-gray-3' : ''"
								title="Option actions"
							>
								<span class="lucide-ellipsis h-3 w-3" />
							</button>
						</template>
					</Dropdown>
				</div>
				<button
					class="flex items-center justify-center gap-1 px-2.5 py-2 text-p-sm text-ink-gray-5 hover:text-ink-gray-8"
					@click="addOption"
				>
					<span class="lucide-plus size-3" aria-hidden="true" />
					Add option
				</button>
			</div>
		</RadioGroup>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from "vue"
import { Dropdown, Radio, RadioGroup } from "frappe-ui"
import Input from "@/components/Input.vue"
import InputLabel from "@/components/InputLabel.vue"
import LucideGripVertical from "~icons/lucide/grip-vertical"
import Block from "@/utils/block"
import { variantOption } from "@/utils/blockTemplate/familyTemplates"
import { getBlockCopy } from "@/utils/serializer"
import { getEditorVariantChoice, setEditorVariantChoice, slug } from "@/utils/variants"
import { confirmKeepVariantOption, variantOptionNames } from "@/utils/variantsEditor"

// The option blocks are the single source of truth: each child carries its own
// `variantOptionName`, so names follow the blocks through delete, duplicate, paste and
// reorder from anywhere. The radio picks what the canvas shows.
const props = defineProps<{ label?: string; block: Block }>()

const options = computed(() => variantOptionNames(props.block))
const shownIndex = computed(() =>
	Math.min(getEditorVariantChoice(props.block.componentId), Math.max(options.value.length - 1, 0)),
)

function rowMenu(index: number) {
	return [
		{ label: "Rename", icon: "lucide-pen-line", onClick: () => startRename(index) },
		{
			label: "Keep only this",
			icon: "lucide-check",
			theme: "red" as const,
			onClick: () => confirmKeepVariantOption(props.block, index),
			condition: () => options.value.length > 1,
		},
		{
			label: "Delete",
			icon: "lucide-trash-2",
			theme: "red" as const,
			onClick: () => deleteOption(index),
			condition: () => options.value.length > 1,
		},
	]
}

// the selection ring follows the swap (ComponentEditor re-anchors to the new
// element), so switching needs no extra highlight here
function showOption(index: number) {
	setEditorVariantChoice(props.block.componentId, index)
}

// a new option starts as a copy of the shown one — a variant is an alternative
// version of what you see. An empty set still gets the placeholder scaffold.
function addOption() {
	const index = props.block.children.length
	const name = `Option ${index + 1}`
	const shown = props.block.children[shownIndex.value]
	const added = props.block.addChild(shown ? getBlockCopy(shown) : variantOption(name), index, false)
	if (added) {
		added.variantOptionName = name
		added.blockName = optionBlockName(name)
	}
	showOption(index)
	startRename(index)
}

// the option's layer name, "option-cards" for a "Cards" option; default names like
// "Option 3" already carry the prefix in their slug
function optionBlockName(name: string) {
	const base = slug(name)
	if (!base) return "option"
	return base.startsWith("option") ? base : `option-${base}`
}

function deleteOption(index: number) {
	const child = props.block.children[index]
	if (child) props.block.removeChild(child)
	const shown = getEditorVariantChoice(props.block.componentId)
	if (shown >= index) setEditorVariantChoice(props.block.componentId, Math.max(0, shown - 1))
}

// -- rename --
const renamingIndex = ref<number | null>(null)

function startRename(index: number) {
	renamingIndex.value = index
}

function focusRenameInput(component: any) {
	nextTick(() => component?.$el?.querySelector?.("input")?.select())
}

function commitRename(index: number, name: string) {
	if (renamingIndex.value !== index) return
	renamingIndex.value = null
	const child = props.block.children[index]
	if (!child || !name.trim()) return
	const previous = options.value[index]
	child.variantOptionName = name.trim()
	// keep the option's layer name in step, unless it was renamed by hand in the tree
	if (!child.blockName || child.blockName === optionBlockName(previous)) {
		child.blockName = optionBlockName(name.trim())
	}
}

// -- drag reorder, the ArrayInput pattern: draggable only while the grip is pressed --
const dragIndex = ref<number | null>(null)
const dragHandleIndex = ref<number | null>(null)

function onDragStart(index: number, event: DragEvent) {
	dragIndex.value = index
	event.dataTransfer?.setData("text/plain", String(index))
	if (event.dataTransfer) event.dataTransfer.effectAllowed = "move"
}

function onDrop(to: number) {
	const from = dragIndex.value
	resetDrag()
	if (from === null || from === to) return
	const children = props.block.children
	const shownChild = children[shownIndex.value]
	const [movedChild] = children.splice(from, 1)
	children.splice(to, 0, movedChild)
	const shownAt = children.indexOf(shownChild)
	if (shownAt !== -1) setEditorVariantChoice(props.block.componentId, shownAt)
}

function resetDrag() {
	dragIndex.value = null
	dragHandleIndex.value = null
}
</script>
