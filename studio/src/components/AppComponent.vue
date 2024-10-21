<template>
	<component
		ref="componentRef"
		:is="components.getComponent(block.componentName)"
		v-bind="componentProps"
		:data-component-id="block.componentId"
		:style="styles"
		v-on="componentEvents"
	>
		<AppComponent v-for="child in block?.children" :key="child.componentId" :block="child" />
	</component>
</template>

<script setup>
import Block from "@/utils/block"
import { computed, onMounted, ref, useAttrs } from "vue"
import { useRouter, useRoute } from "vue-router"
import { createResource } from "frappe-ui"
import components from "@/data/components"
import { getComponentRoot, isDynamicValue, getDynamicValue } from "@/utils/helpers"

import useAppStore from "@/stores/appStore"

const props = defineProps({
	block: {
		type: Block,
		required: true,
	},
})

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

const router = useRouter()
const route = useRoute()
const componentEvents = computed(() => {
	const events = {}
	Object.entries(props.block.componentEvents).forEach(([eventName, event]) => {
		const getEventFn = () => {
			if (event.action === "Switch App Page") {
				return () => {
					router.push({
						name: "AppContainer",
						params: {
							appRoute: route.params.appRoute,
							pageRoute: getPageRoute(route.params.appRoute, event.page),
						},
					})
				}
			} else if (event.action === "Call API") {
				return () => {
					const path = event.api_endpoint.split(".")
					const resource = store.resources[path[0]]

					if (resource) {
						resource[path[1]].submit()
					} else {
						createResource({
							url: event.api_endpoint,
							auto: true,
						})
					}
				}
			}
		}
		events[eventName] = getEventFn()
	})

	return events
})

function getPageRoute(appRoute, page) {
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
