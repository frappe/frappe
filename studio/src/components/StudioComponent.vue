<template>
	<div v-if="error" class="border-ink-red-6 flex flex-col gap-2 border p-2 text-ink-red-6" ref="componentRef">
		<p class="text-sm-semibold">An error occurred while rendering {{ block.componentName }}:</p>
		<pre class="text-xs">{{ error }}</pre>
	</div>

	<StudioComponentWrapper
		v-else-if="block.isStudioComponent"
		:studioComponent="block"
		:evaluationContext="evaluationContext"
		:breakpoint="breakpoint"
	/>
	<StudioComponentEditorWrapper
		v-else-if="isEditingComponent"
		:studioComponent="block"
		:breakpoint="breakpoint"
	/>

	<template v-else-if="block.canHaveChildren()">
		<component
			v-if="showComponent"
			:is="componentName"
			v-bind="componentProps"
			v-on="vModelListeners"
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
			<template
				v-for="(slot, slotName) in block?.componentSlots"
				:key="slotName"
				v-slot:[slotName]="slotProps"
			>
				<template v-if="Array.isArray(slot.slotContent)">
					<StudioComponent
						v-for="slotBlock in slot?.slotContent"
						:key="slotBlock.componentId"
						:block="slotBlock"
						:class="slotClasses"
						:data-slot-id="slot.slotId"
						:data-slot-name="slotName"
						:data-component-id="block.componentId"
						v-bind="slotProps"
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
						v-bind="slotProps"
					/>
				</template>
				<template v-else>
					<div
						:class="[slotClasses, !slot.slotContent ? 'min-h-5 w-full' : '']"
						:data-slot-id="slot.slotId"
						:data-slot-name="slotName"
						:data-component-id="block.componentId"
						v-bind="slotProps"
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
	</template>

	<!-- Rendering separately to avoid empty slots being passed as default slots to components like Dropdown -->
	<template v-else>
		<component
			v-if="showComponent"
			:is="componentName"
			v-bind="componentProps"
			v-on="vModelListeners"
			:data-component-id="block.componentId"
			:data-breakpoint="breakpoint"
			:style="styles"
			:class="classes"
			@mouseover="handleMouseOver"
			@mouseleave="handleMouseLeave"
			@click="handleClick"
			ref="componentRef"
		/>
	</template>

	<teleport to="#overlay" v-if="canvasProps?.overlayElement">
		<!-- prettier-ignore -->
		<ComponentEditor
			v-if="loadEditor"
			ref="editor"
			:block="block.extendedFromComponent || block"
			:breakpoint="breakpoint"
			:isSelected="isSelected"
			:target="(target as HTMLElement)"
		/>
	</teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch, useAttrs, inject, ComputedRef, onErrorCaptured, h } from "vue"
import type { ComponentPublicInstance } from "vue"
import StudioComponentWrapper from "@/components/StudioComponentWrapper.vue"
import ComponentEditor from "@/components/ComponentEditor.vue"
import { customVueComponentsRegistry } from "@/globals"

import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import { getComponentRoot, isHTML, isObjectEmpty } from "@/utils/helpers"
import { isDynamicValue } from "@/utils/code"

import type { CanvasProps } from "@/types/StudioCanvas"
import type { RepeaterContext } from "@/types"
import type HTML from "@/components/AppLayout/HTML.vue"
import MissingComponent from "@/components/MissingComponent.vue"
import useCodeStore from "@/stores/codeStore"

const props = withDefaults(
	defineProps<{
		block: Block
		breakpoint?: string
		isEditingComponent?: boolean
	}>(),
	{
		breakpoint: "desktop",
	},
)

defineOptions({
	inheritAttrs: false,
})

const canvasStore = useCanvasStore()
const codeStore = useCodeStore()

const isComponentReady = ref(false)
const editor = ref<InstanceType<typeof ComponentEditor> | InstanceType<typeof HTML> | null>(null)

const classes = computed(() => {
	return [attrs.class, "__studio_component__", "outline-none", "select-none", ...props.block.getClasses()]
})
const slotClasses = ["__studio_component_slot__", "outline-none", "select-none"]

const canvasProps = inject("canvasProps") as CanvasProps

const styles = computed(() => {
	const _styles = { ...props.block.getStyles(props.breakpoint) }
	Object.entries(_styles).forEach(([key, value]) => {
		if (value) {
			if (isDynamicValue(value.toString())) {
				_styles[key] = codeStore.getDynamicValue(value.toString(), evaluationContext.value)
			}
		}
	})
	return _styles
})

const componentName = computed(() => {
	if (props.block.isContainer()) return props.block.originalElement || "div"

	let name
	if (canvasStore.editingMode === "page") {
		name = props.block.componentName
	} else {
		const proxyComponent = props.block.getProxyComponent()
		name = proxyComponent ? proxyComponent : props.block.componentName
	}

	if (props.block.isCustomVueComponent) {
		name = customVueComponentsRegistry.value[name]
		if (!name) return h(MissingComponent, { componentName: props.block.componentName })
	}
	return name
})

const repeaterContext = inject<ComputedRef<RepeaterContext> | null>("repeaterContext", null)
const componentContext = inject<ComputedRef | null>("componentContext", null)
const evaluationContext = computed(() => {
	return {
		...repeaterContext?.value,
		...componentContext?.value,
	}
})

const getComponentProps = () => {
	if (isObjectEmpty(props.block) || props.block.isRoot()) return []

	const propValues = props.block.getPropsAndAttributes()
	Object.entries(propValues).forEach(([propName, propValue]) => {
		if (propValue?.$type === "variable") {
			propValues[propName] = codeStore.getValueFromVariable(propValue.name, evaluationContext.value)
		} else {
			propValues[propName] = codeStore.evaluateDynamicValues(propValue, evaluationContext.value)
		}
	})
	return propValues
}

// 2-way binding
const vModelListeners = computed(() => {
	if (isObjectEmpty(props.block) || props.block.isRoot()) return {}

	const listeners: Record<string, Function> = {}
	const propValues = props.block.getPropsAndAttributes()

	Object.entries(propValues).forEach(([propName, propValue]) => {
		if (propValue?.$type === "variable") {
			const eventName = `update:${propName}`
			listeners[eventName] = (newValue: any) => {
				codeStore.setValueInVariable(propValue.name, newValue, evaluationContext.value)
			}
		}
	})
	return listeners
})

const attrs = useAttrs()
const componentProps = computed(() => {
	return {
		...getComponentProps(),
		...attrs,
	}
})

const componentRef = ref<ComponentPublicInstance | null>(null)

// visibility
const showComponent = computed(() => {
	if (props.block.visibilityCondition) {
		return codeStore.getDynamicValue(props.block.visibilityCondition, evaluationContext.value)
	}
	return true
})

// block hovering and selection
const isHovered = ref(false)
const isSelected = computed(() => canvasStore.activeCanvas?.selectedBlockIds?.has(props.block.componentId))

const target = computed<HTMLElement | null>(() => {
	if (!componentRef.value) return null
	const root = getComponentRoot(componentRef)
	if (root instanceof HTMLElement || root instanceof SVGElement) return root as HTMLElement
	// Fallback for renderless-root components (Popover root) with $el/$rootRef is undefined/not a DOM element
	// return the real DOM element so the ComponentEditor can anchor to it.
	return document.querySelector(
		`[data-component-id="${props.block.componentId}"][data-breakpoint="${props.breakpoint}"]`,
	) as HTMLElement | null
})

const loadEditor = computed(() => {
	return (
		!props.block.isChildOfComponent &&
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
	const componentId = targetElement
		.closest("[data-component-id]:not(.__studio_component_child__)")
		?.getAttribute("data-component-id")
	if (componentId) {
		return canvasStore.activeCanvas?.findBlock(componentId)
	}
}

const handleClick = (e: MouseEvent) => {
	const block = getClickedComponent(e) || props.block
	canvasStore.activeCanvas?.selectBlock(block, e)
	if (repeaterContext?.value) {
		block.setRepeaterDataItem((repeaterContext.value as RepeaterContext).dataItem)
	}

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
	() => componentRef.value,
	() => {
		if (!componentRef.value) return
		// set data attrs for the components which only bind styles and class to the actual root element
		if (target.value && target.value instanceof Element) {
			target.value?.setAttribute("data-component-id", props.block.componentId)
			target.value?.setAttribute("data-breakpoint", props.breakpoint)
		}
		isComponentReady.value = true
	},
	{ immediate: true },
)

watch(
	() => componentContext?.value,
	(newContext) => {
		if (canvasStore.editingMode === "component" && newContext) {
			props.block.setComponentContext(newContext)
		}
	},
	{ deep: true, immediate: true },
)

const error = ref<Error | null>(null)
onErrorCaptured((err, _instance, info) => {
	const isRouterError = err.message.includes("No match for")
	if (isRouterError || canvasStore.isAIStreaming) {
		error.value = null
		return false
	}
	console.error(
		`Error while rendering StudioComponent ${props.block.componentName} ${props.block.componentId}:\n`,
		`source: ${info}\n`,
		`error: ${err}`,
	)
	error.value = err
	return false
})

watch(componentProps, () => {
	if (error.value) {
		error.value = null
	}
})
</script>
