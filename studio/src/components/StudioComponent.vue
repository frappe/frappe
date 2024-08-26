<template>
	<component
		:is="block.componentName"
		v-bind="{ ...componentData.initialState, ...attrs }"
		:data-component-id="block.componentId"
		:style="styles"
		@mouseover="handleMouseOver"
		@mouseleave="handleMouseLeave"
		@click="handleClick"
		ref="componentRef"
	>
		<StudioComponent v-for="child in block.children" :key="child.componentId" :block="child" />
	</component>

	<teleport to="#overlay" v-if="canvasProps?.overlayElement">
		<ComponentEditor
			ref="editor"
			v-if="loadEditor"
			:block="block"
			:breakpoint="breakpoint"
			:isSelected="isSelected"
			:target="target as HTMLElement"
		/>
	</teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch, inject, useAttrs } from "vue"
import type { ComponentPublicInstance } from "vue"
import ComponentEditor from "@/components/ComponentEditor.vue"

import components from "@/data/components"
import Block from "@/utils/block"
import useStore from "@/store"

const props = defineProps({
	block: {
		type: Block,
		required: true,
	},
	breakpoint: {
		type: String,
		default: "desktop",
	},
})
defineOptions({
	inheritAttrs: false,
})

const attrs = useAttrs()
const store = useStore()
const canvasProps = inject("canvasProps")

const componentData = computed(() => {
	if (props.block.componentName === "div") return { initialState: {} }
	return components.get(props.block.componentName)
})

const styles = computed(() => {
	return props.block.getStyles()
})

const componentRef = ref<ComponentPublicInstance | HTMLElement | SVGElement | null>(null)
const target = computed(() => {
	if (!componentRef.value) return null
	if (componentRef.value instanceof HTMLElement || componentRef.value instanceof SVGAElement) {
		return componentRef.value
	} else {
		return componentRef.value?.$el
	}
})

// block hovering and selection
const isHovered = ref(false)
const isSelected = computed(() => store.selectedBlockIds?.includes(props.block.componentId))

const loadEditor = computed(() => {
	return (
		target.value &&
		props.block.getStyle("display") !== "none" &&
		((isSelected.value && props.breakpoint === store.activeBreakpoint) ||
			(isHovered.value && store.hoveredBreakpoint === props.breakpoint)) &&
		!canvasProps?.scaling &&
		!canvasProps?.panning
	)
})

const handleMouseOver = (e) => {
	store.hoveredBlock = props.block.componentId
	store.hoveredBreakpoint = props.breakpoint
	e.stopPropagation()
}

const handleMouseLeave = (e) => {
	if (store.hoveredBlock === props.block.componentId) {
		store.hoveredBlock = null
		e.stopPropagation()
	}
}

const handleClick = (e: MouseEvent) => {
	store.selectBlock(props.block, e)
	e.stopPropagation()
	e.preventDefault()
}

watch(
	() => store.hoveredBlock,
	(newValue, oldValue) => {
		if (newValue === props.block.componentId) {
			isHovered.value = true
		} else if (oldValue === props.block.componentId) {
			isHovered.value = false
		}
	},
)
</script>
