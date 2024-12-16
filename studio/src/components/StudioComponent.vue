<template>
	<component
		v-if="block.canHaveChildren()"
		:is="block.componentName"
		v-bind="componentProps"
		:data-component-id="block.componentId"
		:style="styles"
		:class="classes"
		@mouseover="handleMouseOver"
		@mouseleave="handleMouseLeave"
		@click="handleClick"
		@contextmenu="triggerContextMenu($event)"
		ref="componentRef"
	>
		<!-- Dynamically render named slots -->
		<template v-for="(slotContent, slotName) in block.componentSlots" :key="slotName" v-slot:[slotName]>
			<template v-if="Array.isArray(slotContent)">
				<div
					:class="slotClasses"
					:data-slot-id="block.getSlotId(slotName)"
					:data-slot-name="slotName"
					:data-component-id="block.componentId"
				>
					<StudioComponent
						v-for="block in slotContent"
						:block="getBlockInstance(block)"
						:class="slotClasses"
					/>
				</div>
			</template>
			<template v-else-if="isHTML(slotContent)">
				<component
					:is="{ template: slotContent }"
					:class="slotClasses"
					:data-slot-id="block.getSlotId(slotName)"
					:data-slot-name="slotName"
					:data-component-id="block.componentId"
				/>
			</template>
			<template v-else>
				<span
					:class="slotClasses"
					:data-slot-id="block.getSlotId(slotName)"
					:data-slot-name="slotName"
					:data-component-id="block.componentId"
					class="min-h-5 min-w-5"
				>
					{{ slotContent }}
				</span>
			</template>
		</template>

		<StudioComponent v-for="child in block?.children" :key="child.componentId" :block="child" />
	</component>

	<!-- Rendering separately to avoid empty slots being passed as default slots to components like Dropdown -->
	<component
		v-else
		:is="block.componentName"
		v-bind="componentProps"
		:data-component-id="block.componentId"
		:style="styles"
		:class="classes"
		@mouseover="handleMouseOver"
		@mouseleave="handleMouseLeave"
		@click="handleClick"
		@contextmenu="triggerContextMenu($event)"
		ref="componentRef"
	/>

	<teleport to="#overlay" v-if="canvasProps?.overlayElement">
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
import { computed, ref, watch, useAttrs, onMounted, nextTick, inject } from "vue"
import type { ComponentPublicInstance } from "vue"
import ComponentEditor from "@/components/ComponentEditor.vue"

import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import { getComponentRoot, isDynamicValue, getDynamicValue, isHTML, getBlockInstance } from "@/utils/helpers"

import { CanvasProps } from "@/types"

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
const editor = ref<InstanceType<typeof ComponentEditor> | null>(null)
const store = useStudioStore()
const classes = ["__studio_component__", "outline-none", "select-none"]
const slotClasses = ["__studio_component_slot__", "outline-none", "select-none"]

const canvasProps = inject("canvasProps") as CanvasProps

const styles = computed(() => {
	return props.block.getStyles()
})

const getComponentProps = () => {
	if (!props.block || props.block.isRoot()) return []

	const componentProps = { ...props.block.componentProps }

	Object.entries(componentProps).forEach(([propName, config]) => {
		if (isDynamicValue(config)) {
			componentProps[propName] = getDynamicValue(config, store.resources)
		}
	})
	return componentProps
}

const attrs = useAttrs()
const componentProps = computed(() => {
	return {
		...getComponentProps(),
		...attrs,
	}
})

const componentRef = ref<ComponentPublicInstance | null>(null)
const target = computed(() => getComponentRoot(componentRef))

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
		!canvasProps?.scaling &&
		!canvasProps?.panning
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
		return store.canvas?.findBlock(componentId)
	}
}

const handleClick = (e: MouseEvent) => {
	const block = getClickedComponent(e) || props.block
	store.selectBlock(block, e)

	if (e.target?.dataset.slotName) {
		store.selectSlot(block, e.target.dataset.slotName)
	}

	e.stopPropagation()
	e.preventDefault()
}

const triggerContextMenu = (e: MouseEvent) => {
	if (props.block.isRoot()) return
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
	const componentRoot = getComponentRoot(componentRef)
	if (componentRoot) {
		componentRoot.setAttribute("data-component-id", props.block.componentId)
		isComponentReady.value = true
	}
})
</script>
