import components from "@/data/components"
import { ComponentProp, ComponentProps } from "@/types"
import { VueProp, VuePropType } from "@/types/vue"

import * as componentTypes from "@/json_types"

function getComponentProps(componentName: string) {
	const props = components.getProps(componentName)
	if (!props) return {}
	const propsConfig: ComponentProps = {}

	if (Array.isArray(props)) {
		props.forEach((prop) => {
			propsConfig[prop] = {
				type: "string",
				default: "",
				inputType: "text",
			}
		})
		return propsConfig
	} else {
		const propTypes = getComponentPropsFromTypescript(componentName)
		Object.entries(props as Record<string, VueProp>).forEach(([propName, prop]) => {
			let propType = getPropType(prop.type)
			if (!propType) {
				propType = propTypes?.[propName]?.type
			}
			const config: ComponentProp = {
				type: propType,
				default: prop.default,
				inputType: getPropInputType(propType),
				required: prop.required,
			}

			if (propType === "String") {
				const enums = getPropEnums(propTypes, propName)
				if (enums) {
					// prop has predefined options
					config.inputType = "select"
					config.options = enums
				}
			}

			propsConfig[propName] = config
		})
	}
	return propsConfig
}

function getPropType(propType: VuePropType | VuePropType[]) {
	if (Array.isArray(propType)) {
		const proptypes = propType.map((type) => type.name)
		const hasNonPrimitiveType = proptypes.find((type) => ["Array", "Object", "Function"].includes(type))
		if (hasNonPrimitiveType) {
			return "Object"
		}
		return "String"
	}
	return propType?.name
}

function getPropInputType(propType: string) {
	propType = propType?.toLowerCase()
	switch (propType) {
		case "string":
			return "text"
		case "number":
			return "number"
		case "boolean":
			return "checkbox"
		case "array":
		case "object":
		case "function":
			return "code"
		default:
			return "text"
	}
}

function getPropEnums(propTypes: object, propName: string): string[] | undefined {
	// fetches prop enums like Button.json > definitions > ButtonProps > properties > variant > enum - ["solid", "subtle", "outline", "ghost"]
	return propTypes?.[propName]?.enum
}

function getComponentPropsFromTypescript(componentName: string) {
	// fetches component properties object from JSON types (converted from TS)
	// e.g.: Button.json > definitions > ButtonProps > properties
	return componentTypes?.[componentName]?.definitions?.[`${componentName}Props`]?.properties
}

// events
function getComponentEvents(componentName: string) {
	return components.getEmits(componentName) || []
}

async function getComponentTemplate(componentName: string): Promise<string> {
	let rawTemplate = null

	if (components.isFrappeUIComponent(componentName)) {
		try {
			// ?raw to get raw content of a file as string
			rawTemplate = await import(`../../../node_modules/frappe-ui/src/components/${componentName}.vue?raw`)
		} catch (error) {
			try {
				// try finding the vue file inside component folder
				rawTemplate = await import(
					`../../../node_modules/frappe-ui/src/components/${componentName}/${componentName}.vue?raw`
				)
			} catch (error) {
				console.error(`Error loading component template ${componentName}:`, error)
				return ""
			}
		}
	} else {
		try {
			// extract studio component template
			rawTemplate = await import(`@/components/AppLayout/${componentName}.vue?raw`)
		} catch (error) {
			console.error(`Error loading component template ${componentName}:`, error)
			return ""
		}
	}
	return rawTemplate?.default || ""
}

async function getComponentSlots(componentName: string) {
	const template = await getComponentTemplate(componentName)
	const slotRegex = /<slot\s*(?:name=["']([^"']*)?["'])?(?:\s*\/>|\s*>(.*?)<\/slot>)?/gi
	const slots = []
	let match

	while ((match = slotRegex.exec(template)) !== null) {
		// Named slot with name attribute
		const namedSlot = match[1]
		// Default/unnamed slot or slot content
		const defaultSlotContent = match[2]

		if (namedSlot) {
			slots.push({
				name: namedSlot,
				type: "named",
				hasDefaultContent: !!defaultSlotContent,
			})
		} else if (defaultSlotContent || match[0].includes("<slot")) {
			slots.push({
				name: "default",
				type: "default",
				hasDefaultContent: !!defaultSlotContent,
			})
		}
	}
	return slots
}

export { getComponentProps, getComponentEvents, getComponentTemplate, getComponentSlots }
