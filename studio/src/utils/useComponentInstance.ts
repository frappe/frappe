import { ref, watch } from "vue"
import Block from "@/utils/block"
import { customVueComponentsRegistry } from "@/globals"

export default function useComponentInstance(blockGetter: () => Block | undefined) {
	const componentInstance = ref<any>({})
	watch(
		() => blockGetter()?.componentName,
		async () => {
			const block = blockGetter()
			if (!block?.componentName || block.isStudioComponent) {
				componentInstance.value = {}
				return
			}
			if (block?.isCustomVueComponent) {
				const asyncComponent = customVueComponentsRegistry.value[block.componentName]
				if (!asyncComponent) return

				const isResolved = typeof asyncComponent.__asyncResolved === "object"
				if (isResolved) {
					componentInstance.value = asyncComponent.__asyncResolved
				} else {
					const resolved = await asyncComponent.__asyncLoader()
					componentInstance.value = resolved.default || resolved
				}
			} else {
				componentInstance.value = window.__APP_COMPONENTS__?.[block.componentName] || {}
			}
		},
		{ immediate: true },
	)
	return componentInstance
}
