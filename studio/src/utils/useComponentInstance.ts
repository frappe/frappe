import { ref, watch } from "vue"
import Block from "@/utils/block"
import { customVueComponentsRegistry } from "@/globals"

async function resolveComponent(component: any) {
	if (!component) return {}
	if (typeof component.__asyncLoader !== "function") return component
	if (typeof component.__asyncResolved === "object") return component.__asyncResolved
	const resolved = await component.__asyncLoader()
	return resolved.default || resolved
}

export default function useComponentInstance(blockGetter: () => Block | undefined) {
	const componentInstance = ref<any>({})
	watch(
		() => blockGetter()?.componentName,
		async () => {
			const block = blockGetter()
			componentInstance.value = {}
			if (!block?.componentName || block.isStudioComponent) {
				return
			}
			if (block?.isCustomVueComponent) {
				const asyncComponent = customVueComponentsRegistry.value[block.componentName]
				if (!asyncComponent) return
				componentInstance.value = await resolveComponent(asyncComponent)
			} else {
				const component = window.__APP_COMPONENTS__?.[block.componentName]
				componentInstance.value = await resolveComponent(component)
			}
		},
		{ immediate: true },
	)
	return componentInstance
}
