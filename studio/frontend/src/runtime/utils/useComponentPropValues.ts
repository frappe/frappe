import { computed } from "vue"
import type Block from "@/runtime/utils/block"
import useComponentStore from "@/runtime/stores/componentStore"
import { usePageScope } from "@/runtime/stores/codeStore"

/**
 * The values a Studio Component instance passes to its host, evaluated where the instance is used.
 * A component without a script takes the defaults of its inputs here. A scripted component
 * declares defaults on its props, and Vue applies them.
 */
export function useComponentPropValues(getBlock: () => Block, getEvaluationContext: () => object) {
	const componentStore = useComponentStore()
	const pageScope = usePageScope()

	return computed(() => {
		const block = getBlock()
		const context = getEvaluationContext()
		const values: Record<string, any> = block.getPropsAndAttributes()
		if (!componentStore.getComponentScript(block.componentName)) {
			for (const prop of componentStore.getComponentProps(block.componentName)) {
				if (!(prop.input_name in values) && prop.default !== undefined) {
					values[prop.input_name] = prop.default
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
