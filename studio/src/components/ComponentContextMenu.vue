<template>
	<div>
		<slot :onContextMenu="showContextMenu" />
		<ContextMenu
			v-if="contextMenuVisible"
			v-on-click-outside="() => (contextMenuVisible = false)"
			:pos-x="posX"
			:pos-y="posY"
			:options="contextMenuOptions"
			@select="handleContextMenuSelect"
		/>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { vOnClickOutside } from "@vueuse/components"
import ContextMenu from "@/components/ContextMenu.vue"
import Block from "@/utils/block"
import { ContextMenuOption } from "@/types"

const props = defineProps<{
	block: Block
	editable: boolean
}>()

const contextMenuVisible = ref(false)
const posX = ref(0)
const posY = ref(0)

const showContextMenu = (e: MouseEvent) => {
	if (props.block.isRoot() || props.editable) return
	contextMenuVisible.value = true
	posX.value = e.pageX
	posY.value = e.pageY
	e.preventDefault()
	e.stopPropagation()
}

const handleContextMenuSelect = (action: CallableFunction) => {
	action()
	contextMenuVisible.value = false
}

const contextMenuOptions: ContextMenuOption[] = [
	{
		label: "Duplicate",
		action: () => props.block.duplicateBlock(),
	},
	{
		label: "Delete",
		action: () => {
			props.block.getParentBlock()?.removeChild(props.block)
		},
		condition: () => {
			return !props.block.isRoot() && Boolean(props.block.getParentBlock())
		},
	},
]
</script>
