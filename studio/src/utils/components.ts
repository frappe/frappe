import components from "@/data/components"
import { ComponentProp, ComponentProps } from "@/types"
import { VueProp, VuePropType } from "@/types/vue"

import * as componentTypes from "@/json_types"
import { parse } from '@vue/compiler-sfc'

function getComponentProps(componentName: string) {
	const props = components.getProps(componentName)
	if (!props) return {}
	const propsConfig: ComponentProps = {}

	if (Array.isArray(props)) {
		props.forEach(prop => {
			propsConfig[prop] = {
				type: "string",
				default: "",
				inputType: "text",
			}
		})
		return propsConfig
	} else {
		Object.entries(props as Record<string, VueProp>).forEach(([propName, prop]) => {
			const propType = getPropType(prop.type)
			const config: ComponentProp = {
				type: propType,
				default: prop.default,
				inputType: getPropInputType(propType),
				required: prop.required,
			}

			if (propType === "String") {
				const enums = getPropEnums(componentName, propName)
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
		const proptypes = propType.map(type => type.name)
		const hasNonPrimitiveType = proptypes.find(type => ["Array", "Object", "Function"].includes(type))
		if (hasNonPrimitiveType) {
			return "Object"
		}
		return "String"
	}
	return propType?.name
}

function getPropInputType(propType: string) {
	switch (propType) {
		case "String":
			return "text"
		case "Number":
			return "number"
		case "Boolean":
			return "checkbox"
		case "Array":
		case "Object":
		case "Function":
			return "code"
		default:
			return "text"
	}
}

function getPropEnums(componentName: string, propName: string): string[] | undefined {
	/**
	 * fetches prop enums like Button.json > definitions > ButtonProps > properties > variant > enum - ["solid", "subtle", "outline", "ghost"]
	 */
	return componentTypes[componentName]?.definitions?.[`${componentName}Props`]?.properties?.[propName]?.enum
}

// events
function getComponentEvents(componentName: string) {
	return components.getEmits(componentName) || []
}

async function getComponentTemplate(componentName: string) {
	let rawTemplate = null

	if (components.isFrappeUIComponent(componentName)) {
		try {
			// ?raw to get raw content of a file as string
			rawTemplate = await import(`../../../node_modules/frappe-ui/src/components/${componentName}.vue?raw`)
		} catch(error) {
			try {
				// try finding the vue file inside component folder
				rawTemplate = await import(`../../../node_modules/frappe-ui/src/components/${componentName}/${componentName}.vue?raw`)
			} catch (error) {
				console.error(`Error loading component template ${componentName}:`, error)
				return ""
			}
		}
	} else {
		try {
			// extract studio component template
			rawTemplate = await import(`../components/AppLayout/${componentName}.vue?raw`)
		} catch (error) {
			console.error(`Error loading component template ${componentName}:`, error)
			return ""
		}
	}
	return rawTemplate?.default || ""
}


async function getComponentSlots(componentName: string) {
	const rawTemplate = await getComponentTemplate(componentName)

	// Extract the template content
	const { descriptor } = parse(rawTemplate)
	const templateContent = descriptor.template?.content || ''

	// Use a DOM parser to help extract slot information
	const tempDiv = document.createElement('div')
	tempDiv.innerHTML = templateContent

	// Find all slot elements
	const slots = Array.from(tempDiv.querySelectorAll('[v-slot], slot, template[v-slot]')).map(el => ({
		name: el.getAttribute('v-slot') || el.getAttribute('name') || 'default',
		content: el.innerHTML.trim()
	}))
	return slots
}


export {
	getComponentProps,
	getComponentEvents,
	getComponentTemplate,
	getComponentSlots,
}