<template>
	<component
		:is="block.componentName"
		v-bind="{ ...componentData.initialState, ...attrs }"
		:data-component-id="block.componentId"
		:style="styles"
		:class="classes"
		@mouseover="handleMouseOver"
		@mouseleave="handleMouseLeave"
		@click="handleClick"
		@contextmenu="triggerContextMenu($event)"
		ref="componentRef"
	>
		<StudioComponent v-for="child in block?.children" :key="child.componentId" :block="child" />
	</component>

	<teleport to="#overlay" v-if="store.canvas?.canvasProps?.overlayElement">
		<!-- prettier-ignore -->
		<ComponentEditor
			v-if="loadEditor"
			ref="editor"
			:block="block"
			:breakpoint="breakpoint"
			:isSelected="isSelected"
			:target="(target as HTMLElement)"
		/>
	</teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch, useAttrs, onMounted, nextTick } from "vue"
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

const isComponentReady = ref(false)
const editor = ref(null)
const attrs = useAttrs()
const store = useStore()

const classes = ["__studio_component__", "outline-none", "select-none"]

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
		isComponentReady.value &&
		props.block.getStyle("display") !== "none" &&
		((isSelected.value && props.breakpoint === store.activeBreakpoint) ||
			(isHovered.value && store.hoveredBreakpoint === props.breakpoint)) &&
		!store.canvas.canvasProps?.scaling &&
		!store.canvas.canvasProps?.panning
	)
})

const handleMouseOver = (e: MouseEvent) => {
	store.hoveredBlock = props.block.componentId
	store.hoveredBreakpoint = props.breakpoint
	e.stopPropagation()
}

const handleMouseLeave = (e: MouseEvent) => {
	if (store.hoveredBlock === props.block.componentId) {
		store.hoveredBlock = null
		e.stopPropagation()
	}
}

const getClickedComponent = (e: MouseEvent) => {
	const targetElement = e.target as HTMLElement
	const componentId = targetElement.closest("[data-component-id]")?.getAttribute("data-component-id")
	if (componentId) {
		return store.canvas.findBlock(componentId)
	}
}

const handleClick = (e: MouseEvent) => {
	const block = getClickedComponent(e)
	if (block) {
		store.selectBlock(block, e)
	} else {
		store.selectBlock(props.block, e)
	}
	e.stopPropagation()
	e.preventDefault()
}

const triggerContextMenu = (e: MouseEvent) => {
	e.stopPropagation()
	e.preventDefault()

	const block = getClickedComponent(e) || props.block
	store.selectBlock(block, e)

	nextTick(() => {
		editor.value?.element.dispatchEvent(new MouseEvent("contextmenu", e))
	})
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

watch(
	() => props.block.baseStyles,
	() => {
		if (!componentRef.value) return
		// update styles when baseStyles change for frappeui components with inheritAttrs: false
		const styles = props.block.getStyles()
		for (const key in styles) {
			componentRef.value?.$el?.style.setProperty(key, styles[key])
		}
	},
	{ deep: true },
)

onMounted(() => {
	// set data-component-id on mount since some frappeui components have inheritAttrs: false
	if (componentRef.value) {
		componentRef.value?.$el?.setAttribute("data-component-id", props.block.componentId)
		isComponentReady.value = true
	}
})
</script>
