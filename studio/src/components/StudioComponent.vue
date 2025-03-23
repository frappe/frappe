<template>
	<component
		v-if="block.canHaveChildren()"
		:is="componentName"
		v-bind="componentProps"
		v-model="boundValue"
		:data-component-id="block.componentId"
		:data-breakpoint="breakpoint"
		:style="styles"
		:class="classes"
		@mouseover="handleMouseOver"
		@mouseleave="handleMouseLeave"
		@click="handleClick"
		ref="componentRef"
	>
		<!-- Dynamically render named slots -->
		<template v-for="(slot, slotName) in block?.componentSlots" :key="slotName" v-slot:[slotName]>
			<template v-if="Array.isArray(slot.slotContent)">
				<StudioComponent
					v-for="slotBlock in slot?.slotContent"
					:key="slotBlock.componentId"
					:block="slotBlock"
					:class="slotClasses"
					:data-slot-id="slot.slotId"
					:data-slot-name="slotName"
					:data-component-id="block.componentId"
				/>
			</template>
			<template v-else-if="isHTML(slot.slotContent)">
				<component
					v-memo="[slot.slotContent]"
					:is="{ template: slot.slotContent }"
					:class="slotClasses"
					:data-slot-id="slot.slotId"
					:data-slot-name="slotName"
					:data-component-id="block.componentId"
				/>
			</template>
			<template v-else>
				<div
					:class="[slotClasses, !slot.slotContent ? 'min-h-5 w-full' : '']"
					:data-slot-id="slot.slotId"
					:data-slot-name="slotName"
					:data-component-id="block.componentId"
				>
					{{ slot.slotContent }}
				</div>
			</template>
		</template>

		<StudioComponent
			v-for="child in block?.children"
			:key="child.componentId"
			:block="child"
			:breakpoint="breakpoint"
		/>
	</component>

	<!-- Rendering separately to avoid empty slots being passed as default slots to components like Dropdown -->
	<component
		v-else
		:is="block.componentName"
		v-bind="componentProps"
		v-model="boundValue"
		:data-component-id="block.componentId"
		:data-breakpoint="breakpoint"
		:style="styles"
		:class="classes"
		@mouseover="handleMouseOver"
		@mouseleave="handleMouseLeave"
		@click="handleClick"
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
import { computed, ref, watch, useAttrs, inject } from "vue"
import type { ComponentPublicInstance } from "vue"
import ComponentEditor from "@/components/ComponentEditor.vue"

import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { getComponentRoot, isDynamicValue, getDynamicValue, isHTML } from "@/utils/helpers"

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

const store = useStudioStore()
const canvasStore = useCanvasStore()

const isComponentReady = ref(false)
const editor = ref<InstanceType<typeof ComponentEditor> | null>(null)

const classes = ["__studio_component__", "outline-none", "select-none"]
const slotClasses = ["__studio_component_slot__", "outline-none", "select-none"]

const canvasProps = inject("canvasProps") as CanvasProps

const styles = computed(() => {
	return props.block.getStyles()
})

const componentName = computed(() => {
	if (canvasStore.editingMode === "page") return props.block.componentName
	const proxyComponent = props.block.getProxyComponent()
	return proxyComponent ? proxyComponent : props.block.componentName
})

const getComponentProps = () => {
	if (!props.block || props.block.isRoot()) return []

	const componentProps = { ...props.block.componentProps }

	Object.entries(componentProps).forEach(([propName, config]) => {
		if (isDynamicValue(config)) {
			componentProps[propName] = getDynamicValue(config, { ...store.resources, ...store.variables })
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
const target = ref<HTMLElement | null>(null)

// Computed property for v-model binding
const boundValue = computed({
	get() {
		const modelValue = props.block.componentProps.modelValue
		if (modelValue?.$type === "variable") {
			// Return the variable value from the store
			return store.variables[modelValue.name]
		}
		// Return the plain value if not bound to a variable
		return modelValue
	},
	set(newValue) {
		const modelValue = props.block.componentProps.modelValue
		if (modelValue?.$type === "variable") {
			// Update the variable in the store
			store.variables[modelValue.name] = newValue
		} else {
			// Update the prop directly if not bound to a variable
			props.block.setProp("modelValue", newValue)
		}
	},
})

// block hovering and selection
const isHovered = ref(false)
const isSelected = computed(() => canvasStore.activeCanvas?.selectedBlockIds?.has(props.block.componentId))

const loadEditor = computed(() => {
	return (
		target.value &&
		isComponentReady.value &&
		props.block.getStyle("display") !== "none" &&
		((isSelected.value && props.breakpoint === canvasStore.activeCanvas?.activeBreakpoint) ||
			(isHovered.value && canvasStore.activeCanvas?.hoveredBreakpoint === props.breakpoint)) &&
		!canvasProps?.scaling &&
		!canvasProps?.panning
	)
})

const handleMouseOver = (e: MouseEvent) => {
	canvasStore.activeCanvas?.setHoveredBlock(props.block.componentId)
	canvasStore.activeCanvas?.setHoveredBreakpoint(props.breakpoint)
	e.stopPropagation()
}

const handleMouseLeave = (e: MouseEvent) => {
	if (canvasStore.activeCanvas?.hoveredBlock === props.block.componentId) {
		canvasStore.activeCanvas.setHoveredBlock(null)
		e.stopPropagation()
	}
}

const getClickedComponent = (e: MouseEvent) => {
	const targetElement = e.target as HTMLElement
	const componentId = targetElement.closest("[data-component-id]")?.getAttribute("data-component-id")
	if (componentId) {
		return canvasStore.activeCanvas?.findBlock(componentId)
	}
}

const handleClick = (e: MouseEvent) => {
	const block = getClickedComponent(e) || props.block
	canvasStore.activeCanvas?.selectBlock(block, e)

	const slotName = (e.target as HTMLElement).dataset.slotName
	if (slotName) {
		const slot = block.getSlot(slotName)
		if (slot) {
			canvasStore.activeCanvas?.selectSlot(slot)
		}
	}

	e.stopPropagation()
	e.preventDefault()
}

watch(
	() => canvasStore.activeCanvas?.hoveredBlock,
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

watch(
	() => componentRef.value,
	() => {
		if (!componentRef.value) return
		// set data-component-id on update since some frappeui components have inheritAttrs: false
		target.value = getComponentRoot(componentRef)
		if (target.value) {
			target.value?.setAttribute("data-component-id", props.block.componentId)
			isComponentReady.value = true
		}
	},
	{ immediate: true },
)
</script>
