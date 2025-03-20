<template>
	<component
		ref="componentRef"
		v-show="showComponent"
		:is="components.getComponent(block.componentName)"
		v-bind="componentProps"
		v-model="boundValue"
		:data-component-id="block.componentId"
		:style="styles"
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
import { computed, onMounted, ref, useAttrs } from "vue"
import { useRouter, useRoute } from "vue-router"
import { createResource } from "frappe-ui"
import components from "@/data/components"
import { getComponentRoot, isDynamicValue, getDynamicValue, isHTML, executeUserScript } from "@/utils/helpers"

import useAppStore from "@/stores/appStore"
import { toast } from "vue-sonner"

const props = defineProps<{
	block: Block
}>()

const componentRef = ref(null)
const styles = computed(() => props.block.getStyles())

const store = useAppStore()
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

// visibility
const showComponent = computed(() => {
	if (props.block.visibilityCondition) {
		const value = getDynamicValue(props.block.visibilityCondition, { ...store.resources, ...store.variables })
		return typeof value === "string" ? value === "true" : value
	}
	return true
})

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
					const fields = {}
					event.fields.forEach((field) => {
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
					executeUserScript(event.script, store.variables, store.resources)
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
	// set data-component-id on mount since some frappeui components have inheritAttrs: false
	const componentRoot = getComponentRoot(componentRef)
	if (componentRoot) {
		componentRoot.setAttribute("data-component-id", props.block.componentId)
	}
})
</script>
