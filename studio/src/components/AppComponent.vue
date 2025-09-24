<template>
	<StudioComponentRenderer
		v-if="block.isStudioComponent"
		:studioComponent="block"
		:evaluationContext="evaluationContext"
	/>
	<component
		v-else
		ref="componentRef"
		v-show="showComponent"
		:is="componentName"
		v-bind="componentProps"
		v-model="boundValue"
		:data-component-id="block.componentId"
		:style="styles"
		:class="classes"
		v-on="componentEvents"
	>
		<!-- Dynamically render named slots -->
		<template v-for="(slot, slotName) in block.componentSlots" :key="slotName" v-slot:[slotName]>
			<template v-if="Array.isArray(slot.slotContent)">
				<AppComponent v-for="slotBlock in slot.slotContent" :block="slotBlock" :key="slotBlock.componentId" />
			</template>
			<template v-else-if="isHTML(slot.slotContent)">
				<component :is="{ template: slot.slotContent }" />
			</template>
			<template v-else>
				{{ slot.slotContent }}
			</template>
		</template>

		<AppComponent v-for="child in block?.children" :key="child.componentId" :block="child" />
	</component>
</template>

<script setup lang="ts">
import Block from "@/utils/block"
import { computed, onMounted, ref, useAttrs, inject, type ComputedRef, toRefs } from "vue"
import type { ComponentPublicInstance } from "vue"
import { useRouter, useRoute } from "vue-router"
import { createResource } from "frappe-ui"
import {
	getComponentRoot,
	isDynamicValue,
	getDynamicValue,
	isHTML,
	executeUserScript,
	getValueFromObject,
	setValueInObject,
	getAPIParams,
} from "@/utils/helpers"
import { useScreenSize } from "@/utils/useScreenSize"

import useAppStore from "@/stores/appStore"
import { toast } from "vue-sonner"
import type { Field } from "@/types/ComponentEvent"
import type { DataResult } from "@/types/Studio/StudioResource"

import StudioComponentRenderer from "@/components/StudioComponentRenderer.vue"

const props = defineProps<{
	block: Block
}>()

const componentName = computed(() => {
	if (props.block.isContainer()) return "div"
	return props.block.componentName
})

const componentRef = ref<ComponentPublicInstance | null>(null)

const { currentBreakpoint } = useScreenSize()
const styles = computed(() => {
	const _styles = props.block.getStyles(currentBreakpoint.value)
	Object.entries(_styles).forEach(([key, value]) => {
		if (value) {
			if (isDynamicValue(value.toString())) {
				_styles[key] = getDynamicValue(value.toString(), evaluationContext.value)
			}
		}
	})
	return _styles
})
const classes = computed(() => {
	return [attrs.class, ...props.block.getClasses()]
})

const store = useAppStore()
const repeaterContext = inject("repeaterContext", {})
const componentContext = inject<ComputedRef | null>("componentContext", null)

const evaluationContext = computed(() => {
	return {
		...store.variables,
		...store.resources,
		...repeaterContext,
		...componentContext?.value,
		route: store.routeObject,
	}
})

const getComponentProps = () => {
	if (!props.block || props.block.isRoot()) return []

	const propValues = { ...props.block.componentProps }
	delete propValues.modelValue

	Object.entries(propValues).forEach(([propName, config]) => {
		if (isDynamicValue(config)) {
			propValues[propName] = getDynamicValue(config, evaluationContext.value)
		}
	})
	return propValues
}

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
		const value = getDynamicValue(props.block.visibilityCondition, evaluationContext.value)
		// Handle different return types:
		// - Boolean: return as-is
		// - String "true"/"false": convert to boolean
		// - Other values: check truthiness
		if (typeof value === "boolean") {
			return value
		} else if (typeof value === "string" && (value === "true" || value === "false")) {
			return value === "true"
		} else {
			return value
		}
	}
	return true
})

// modelValue binding
const boundValue = computed({
	get() {
		const modelValue = props.block.componentProps.modelValue
		if (modelValue?.$type === "variable") {
			return getValueFromObject(store.variables, modelValue.name)
		} else if (isDynamicValue(modelValue)) {
			return getDynamicValue(modelValue, evaluationContext.value)
		}
		return modelValue
	},
	set(newValue) {
		const modelValue = props.block.componentProps.modelValue
		if (modelValue?.$type === "variable") {
			setValueInObject(store.variables, modelValue.name, newValue)
		} else {
			// update the prop directly if not bound to a variable
			props.block.setProp("modelValue", newValue)
		}
	},
})

// events
const router = useRouter()
const route = useRoute()

const componentEvents = computed(() => {
	const events: Record<string, Function | undefined> = {}
	Object.entries(props.block.componentEvents).forEach(([eventName, event]) => {
		const getEventFn = () => {
			if (event.action === "Switch App Page") {
				return () => {
					router.push({
						name: "AppContainer",
						params: {
							appRoute: route.params.appRoute,
							pageRoute: getPageRoute(route.params.appRoute as string, event.page),
						},
					})
				}
			} else if (event.action === "Call API") {
				return () => {
					const path: string[] = event.api_endpoint.split(".")
					// get resource
					const resource = store.resources[path[0]]

					if (resource) {
						// access and call whitelisted method
						resource[path[1]].submit()
					} else {
						createResource({
							url: event.api_endpoint,
							auto: true,
							params: getAPIParams(event.params, evaluationContext.value),
							onSuccess: handleSuccess(event),
							onError: handleError(event),
						})
					}
				}
			} else if (event.action === "Insert a Document") {
				return () => {
					const fields: Record<string, any> = {}
					event.fields.forEach((field: Field) => {
						fields[field.field] = getValueFromObject(store.variables, field.value)
					})
					createResource({
						url: "frappe.client.insert",
						method: "POST",
						params: {
							doc: {
								doctype: event.doctype,
								...fields,
							},
						},
						onSuccess: handleSuccess(event),
						onError: handleError(event),
					}).submit()
				}
			} else if (event.action === "Run Script") {
				return () => {
					executeUserScript(
						event.script,
						store.variables,
						store.resources,
						repeaterContext,
						componentContext?.value,
					)
				}
			}
		}
		events[eventName] = getEventFn()
	})

	return events
})

// Helper functions for handling success and error responses
const handleSuccess = (event: any) => (data: DataResult) => {
	if (event.on_success === "script") {
		if (event.on_success_script) {
			const variablesRefs = toRefs(store.variables)
			const context = {
				...variablesRefs,
				...store.resources,
				...repeaterContext,
				...componentContext?.value,
				data,
			}
			const successFn = new Function(
				"ctx",
				`with(ctx) {
					${event.on_success_script}
					return onSuccess(data);
				}`,
			)
			return successFn(context)
		}
	} else {
		if (event.action === "Insert a Document") {
			toast.success(event.success_message || `${event.doctype} created successfully`)
		} else if (event.action === "Call API" && event.success_message) {
			toast.success(event.success_message)
		}
	}
}

const handleError = (event: any) => (error: any) => {
	if (event.on_error === "script") {
		if (event.on_error_script) {
			const variablesRefs = toRefs(store.variables)
			const context = {
				...variablesRefs,
				...store.resources,
				...repeaterContext,
				...componentContext?.value,
				error,
			}
			const errorFn = new Function(
				"ctx",
				`with(ctx) {
					${event.on_error_script}
					return onError(error);
				}`,
			)
			return errorFn(context)
		}
	} else {
		if (event.action === "Insert a Document") {
			toast.error(event.error_message || `Error creating ${event.doctype}`)
		} else if (event.action === "Call API" && event.error_message) {
			toast.error(event.error_message)
		}
	}
}

function getPageRoute(appRoute: string, page: string) {
	// extract page route from full page route
	return page.replace(`studio-app/${appRoute}/`, "")
}

onMounted(() => {
	const componentRoot = getComponentRoot(componentRef)
	if (componentRoot) {
		// explicitly set data-component-id for frappeui components with inheritAttrs: false
		componentRoot.setAttribute("data-component-id", props.block.componentId)
	}
})
</script>
