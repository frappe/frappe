import { computed } from "vue"
import type Block from "@/utils/block"
import useComponentStore from "@/stores/componentStore"
import { usePageScope } from "@/stores/codeStore"

/**
 * The values a Studio Component instance passes to its host, evaluated where the instance is used.
 * A component without a script takes the defaults of its inputs here. A scripted component
 * declares defaults on its props, and Vue applies them.
 */
export function useComponentInputValues(getBlock: () => Block, getEvaluationContext: () => object) {
	const componentStore = useComponentStore()
	const pageScope = usePageScope()

	return computed(() => {
		const block = getBlock()
		const context = getEvaluationContext()
		const values: Record<string, any> = block.getPropsAndAttributes()
		if (!componentStore.getComponentScript(block.componentName)) {
			for (const input of componentStore.getComponentInputs(block.componentName)) {
				if (!(input.input_name in values) && input.default !== undefined) {
					values[input.input_name] = input.default
				}
			}
		}
		for (const [name, value] of Object.entries(values)) {
			values[name] =
				value?.$type === "variable"
					? pageScope.getValueFromVariable(value.name, context)
					: pageScope.evaluateDynamicValues(value, context)
		}
		return values
	})
}
