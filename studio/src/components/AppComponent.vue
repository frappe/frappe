<template>
	<StudioComponentRenderer
		v-if="block.isStudioComponent"
		:studioComponent="block"
		:evaluationContext="evaluationContext"
	/>
	<template v-else-if="block.canHaveChildren()">
		<component
			ref="componentRef"
			v-if="showComponent"
			:is="componentName"
			v-bind="componentProps"
			v-on="mergedListeners"
			:data-component-id="block.componentId"
			:style="styles"
			:class="classes"
		>
			<!-- Dynamically render named slots -->
			<template
				v-for="(slot, slotName) in block.componentSlots"
				:key="slotName"
				v-slot:[slotName]="slotProps"
			>
				<template v-if="Array.isArray(slot.slotContent)">
					<AppComponent
						v-for="slotBlock in slot.slotContent"
						:block="slotBlock"
						:key="slotBlock.componentId"
						v-bind="slotProps"
					/>
				</template>
				<template v-else-if="isHTML(slot.slotContent)">
					<component :is="{ template: slot.slotContent }" v-bind="slotProps" />
				</template>
				<template v-else v-bind="slotProps">
					{{ slot.slotContent }}
				</template>
			</template>

			<AppComponent v-for="child in block?.children" :key="child.componentId" :block="child" />
		</component>
	</template>

	<!-- Rendering separately to avoid empty slots being passed as default slots to components like Dropdown -->
	<template v-else>
		<component
			ref="componentRef"
			v-if="showComponent"
			:is="componentName"
			v-bind="componentProps"
			v-on="mergedListeners"
			:data-component-id="block.componentId"
			:style="styles"
			:class="classes"
		/>
	</template>
</template>

<script setup lang="ts">
import Block from "@/utils/block"
import { computed, onMounted, ref, useAttrs, inject, type ComputedRef, h } from "vue"
import type { ComponentPublicInstance } from "vue"
import { createResource } from "frappe-ui"
import { getComponentRoot, isHTML, isObjectEmpty } from "@/utils/helpers"
import { useScreenSize } from "@/utils/useScreenSize"
import { isDynamicValue } from "@/utils/code"
import { resolveEventListener } from "@/utils/eventModifiers"
import useComponentInstance from "@/utils/useComponentInstance"

import useCodeStore from "@/stores/codeStore"
import { toast } from "frappe-ui"
import type { RepeaterContext } from "@/types"
import type { Field } from "@/types/ComponentEvent"
import type { DataResult } from "@/types/Studio/StudioResource"

import StudioComponentRenderer from "@/components/StudioComponentRenderer.vue"
import { customVueComponentsRegistry } from "@/globals"
import MissingComponent from "@/components/MissingComponent.vue"

const props = defineProps<{
	block: Block
}>()

const componentName = computed(() => {
	if (props.block.isContainer()) return props.block.originalElement || "div"
	let name = props.block.componentName
	if (window.is_preview && props.block.isCustomVueComponent) {
		name = customVueComponentsRegistry.value[name]
		if (!name) return h(MissingComponent, { componentName: props.block.componentName })
	}
	return name
})

const componentRef = ref<ComponentPublicInstance | null>(null)

const { currentBreakpoint } = useScreenSize()
const styles = computed(() => {
	const _styles = props.block.getStyles(currentBreakpoint.value)
	Object.entries(_styles).forEach(([key, value]) => {
		if (value) {
			if (isDynamicValue(value.toString())) {
				_styles[key] = codeStore.getDynamicValue(value.toString(), evaluationContext.value)
			}
		}
	})
	return _styles
})
const classes = computed(() => {
	return [attrs.class, ...props.block.getClasses()]
})

const codeStore = useCodeStore()
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

// visibility
const showComponent = computed(() => {
	if (props.block.visibilityCondition) {
		return codeStore.getDynamicValue(props.block.visibilityCondition, evaluationContext.value)
	}
	return true
})

// events
type Listener = (...args: any[]) => any
type ListenerMap = Record<string, Listener | Listener[]>

const componentInstance = useComponentInstance(() => props.block)
const componentEmits = computed<string[]>(() => componentInstance.value?.emits || [])

const componentEvents = computed(() => {
	const events: ListenerMap = {}
	Object.entries(props.block.componentEvents).forEach(([eventName, event]) => {
		const handler = getEventHandler(event)
		if (!handler) return
		const { name, listener } = resolveEventListener(eventName, handler, componentEmits.value)
		addListener(events, name, listener)
	})
	return events
})

function getEventHandler(event: any): Listener | undefined {
	if (event.action === "Insert a Document") {
		return (...eventArgs: any[]) => {
			const fields: Record<string, any> = {}
			event.fields.forEach((field: Field) => {
				fields[field.field] = codeStore.getValueFromVariable(field.value, evaluationContext.value)
			})
			event.eventArgs = eventArgs
			createResource({
				url: "frappe.client.insert",
				method: "POST",
				params: { doc: { doctype: event.doctype, ...fields } },
				onSuccess: handleSuccess(event),
				onError: handleError(event),
			}).submit()
		}
	} else if (event.action === "Run Script") {
		return (...eventArgs: any[]) => {
			codeStore.executeUserScript(event.script, repeaterContext?.value, componentContext?.value, eventArgs)
		}
	}
}

const mergedListeners = computed(() => {
	const merged: ListenerMap = {}
	for (const [name, listener] of Object.entries(vModelListeners.value)) {
		addListener(merged, name, listener as Listener)
	}
	for (const [name, listener] of Object.entries(componentEvents.value)) {
		const handlers = Array.isArray(listener) ? listener : [listener]
		handlers.forEach((handler) => addListener(merged, name, handler))
	}
	return merged
})

function addListener(map: ListenerMap, name: string, listener: Listener) {
	const existing = map[name]
	if (!existing) {
		map[name] = listener
	} else if (Array.isArray(existing)) {
		existing.push(listener)
	} else {
		map[name] = [existing, listener]
	}
}

const handleSuccess = (event: any) => (data: DataResult) => {
	if (event.on_success === "script" && event.on_success_script) {
		return codeStore.handleSuccess(
			event.on_success_script,
			data,
			repeaterContext?.value,
			componentContext?.value,
			event.eventArgs,
		)
	} else {
		if (event.action === "Insert a Document") {
			toast.success(event.success_message || `${event.doctype} created successfully`)
		}
	}
}

const handleError = (event: any) => (error: any) => {
	if (event.on_error === "script" && event.on_error_script) {
		return codeStore.handleError(
			event.on_error_script,
			error,
			repeaterContext?.value,
			componentContext?.value,
			event.eventArgs,
		)
	} else {
		if (event.action === "Insert a Document") {
			toast.error(event.error_message || `Error creating ${event.doctype}`)
		}
	}
}

onMounted(() => {
	const componentRoot = getComponentRoot(componentRef)
	if (componentRoot) {
		// explicitly set data-component-id for frappeui components with inheritAttrs: false
		componentRoot.setAttribute("data-component-id", props.block.componentId)
	}
})
</script>
