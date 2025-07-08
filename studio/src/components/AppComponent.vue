<template>
	<component
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
import { computed, onMounted, ref, useAttrs, inject } from "vue"
import type { ComponentPublicInstance } from "vue"
import { useRouter, useRoute } from "vue-router"
import { createResource } from "frappe-ui"
import { getComponentRoot, isDynamicValue, getDynamicValue, isHTML, executeUserScript } from "@/utils/helpers"
import { useScreenSize } from "@/utils/useScreenSize"

import useAppStore from "@/stores/appStore"
import { toast } from "vue-sonner"
import type { Field } from "@/types/ComponentEvent"

const props = defineProps<{
	block: Block
}>()

const componentName = computed(() => {
	if (props.block.isContainer()) return "div"
	return props.block.componentName
})

const componentRef = ref<ComponentPublicInstance | null>(null)

const { currentBreakpoint } = useScreenSize()
const styles = computed(() => props.block.getStyles(currentBreakpoint.value))
const classes = computed(() => {
	return [attrs.class, ...props.block.getClasses()]
})

const repeaterContext = inject("repeaterContext", {})
const store = useAppStore()

const getEvaluationContext = () => {
	return {
		...store.variables,
		...store.resources,
		...repeaterContext,
	}
}

const getComponentProps = () => {
	if (!props.block || props.block.isRoot()) return []

	const propValues = { ...props.block.componentProps }
	delete propValues.modelValue

	Object.entries(propValues).forEach(([propName, config]) => {
		if (isDynamicValue(config)) {
			propValues[propName] = getDynamicValue(config, getEvaluationContext())
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
		const value = getDynamicValue(props.block.visibilityCondition, getEvaluationContext())
		return typeof value === "string" ? value === "true" : value
	}
	return true
})

// modelValue binding
const boundValue = computed({
	get() {
		const modelValue = props.block.componentProps.modelValue
		if (modelValue?.$type === "variable") {
			// handle nested object properties
			const propertyPath = modelValue.name.split(".")
			let value = store.variables
			// return nested object property value
			for (const key of propertyPath) {
				if (value === undefined || value === null) return undefined
				value = value[key]
			}
			return value
		} else if (isDynamicValue(modelValue)) {
			return getDynamicValue(modelValue, getEvaluationContext())
		}
		return modelValue
	},
	set(newValue) {
		const modelValue = props.block.componentProps.modelValue
		if (modelValue?.$type === "variable") {
			// update the variable in the store
			const propertyPath = modelValue.name.split(".")
			if (propertyPath.length === 1) {
				// top level variable
				store.variables[modelValue.name] = newValue
			} else {
				// nested object properties
				const targetProperty = propertyPath.pop()!
				let obj = store.variables

				// navigate to the parent object
				for (const key of propertyPath) {
					if (!obj[key] || typeof obj[key] !== "object") {
						obj[key] = {}
					}
					obj = obj[key]
				}
				// set the value on the parent object
				obj[targetProperty] = newValue
			}
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
						})
					}
				}
			} else if (event.action === "Insert a Document") {
				return () => {
					const fields: Record<string, any> = {}
					event.fields.forEach((field: Field) => {
						fields[field.field] = store.variables[field.value]
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
						onSuccess() {
							if (event.success_message) {
								toast.success(event.success_message)
							} else {
								toast.success(`${event.doctype} saved successfully`)
							}
						},
						onError() {
							if (event.error_message) {
								toast.error(event.error_message)
							} else {
								toast.error(`Error saving ${event.doctype}`)
							}
						},
					}).submit()
				}
			} else if (event.action === "Run Script") {
				return () => {
					executeUserScript(event.script, store.variables, store.resources, repeaterContext)
				}
			}
		}
		events[eventName] = getEventFn()
	})

	return events
})

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
