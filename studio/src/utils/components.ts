import components from "@/data/components"
import type { ComponentProp, ComponentProps } from "@/types"
import type { VueProp, VuePropType } from "@/types/vue"

import * as jsonTypes from "@/json_types"
import { isObjectEmpty } from "@/utils/helpers"
import { ConcreteComponent } from "vue"

interface ComponentTypes {
	[componentName: string]: {
		definitions: Record<string, any>
	}
}
const componentTypes = jsonTypes as ComponentTypes

const componentFolders: Record<string, string> = {
	DateTimePicker: "DatePicker",
	DateRangePicker: "DatePicker",
}

function getComponentProps(componentName: string, component: ConcreteComponent | string): ComponentProps {
	if (typeof component === "string") return {}
	const props = component.props
	if (!props) return {}

	if ("modelModifiers" in props) {
		delete props.modelModifiers
	}

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
		let folderName = componentFolders[componentName] || componentName
		const componentDefinitions = getComponentDefinitions(folderName)
		const componentSchema = componentDefinitions?.[`${folderName}Props`]
		const { required, properties } = componentSchema || {}

		Object.entries(props as Record<string, VueProp>).forEach(([propName, prop]) => {
			let propType = getPropType(prop.type)
			let isRequired = prop.required
			const propertySchema = properties?.[propName]

			if (!propType && !isObjectEmpty(propertySchema)) {
				isRequired = required?.includes(propName)

				if ("anyOf" in propertySchema) {
					// prop has multiple types
					const propTypes = propertySchema?.anyOf.map((prop: Record<string, any>) => prop?.type)
					propType = getSinglePropType(propTypes)
				} else {
					propType = propertySchema?.type
					if (!propType && propertySchema?.$ref) {
						// handle referenced types
						const refName = propertySchema.$ref.split("/").pop()
						const refType = componentDefinitions?.[refName]?.type
						propType = refType || "object"
					}
				}
			}

			if (typeof propType === "string") {
				propType = propType?.toLowerCase()
			}

			const config: ComponentProp = {
				type: propType,
				default: prop.default,
				inputType: getPropInputType(propType),
				required: isRequired,
			}

			if (propType === "string") {
				const enums = getPropEnums(properties, componentDefinitions, propName)
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
		const proptypes = propType.map((type) => type?.name)
		return getSinglePropType(proptypes)
	}
	return propType?.name
}

function getPropInputType(propType: string) {
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

function getPropEnums(properties: Record<string, any>, componentDefinitions: Record<string, any>, propName: string): string[] | undefined {
	// fetches prop enums like Button.json > definitions > ButtonProps > properties > variant > enum - ["solid", "subtle", "outline", "ghost"]
	const propertySchema = properties?.[propName]
	if (!propertySchema) return undefined

	if (propertySchema.enum) {
		return propertySchema.enum
	}
	if (propertySchema.$ref) {
		const refName = propertySchema.$ref.split("/").pop()
		return componentDefinitions?.[refName]?.enum
	}
	return undefined
}

function getComponentDefinitions(componentName: string) {
	// fetches component type definitions object from JSON types (converted from TS)
	// e.g.: Button.json > definitions
	return componentTypes?.[componentName]?.definitions
}

function getSinglePropType(propTypes: string | string[]) {
	if (typeof propTypes === "string") return propTypes
	const hasNonPrimitiveType = propTypes.find((type: string) => ["array", "object", "function"].includes(type.toLowerCase()))
	if (hasNonPrimitiveType) {
		return "object"
	}
	return "string"
}

// ?raw to get raw content of a file as string
const frappeUIModules: Record<string, string> = import.meta.glob(
	[
		"../../../node_modules/frappe-ui/src/components/**/*.vue",
		"!**/*.story.vue",
	],
	{ query: "?raw", eager: true, import: "default" }
)

const studioModules: Record<string, string> = import.meta.glob(
	"@/components/AppLayout/*.vue",
	{ query: "?raw", eager: true, import: "default" }
)

const templateCache = new Map<string, string>()

function getComponentTemplate(componentName: string): string {
	if (templateCache.has(componentName)) {
		return templateCache.get(componentName) || ""
	}

	let rawTemplate = ""

	if (components.isFrappeUIComponent(componentName)) {
		try {
			let modulePath = `../../../node_modules/frappe-ui/src/components/${componentName}.vue`
			if (frappeUIModules[modulePath]) {
				rawTemplate = frappeUIModules[modulePath]
			} else {
				// try finding the vue file inside component folder
				const folderName = componentFolders[componentName] || componentName
				modulePath = `../../../node_modules/frappe-ui/src/components/${folderName}/${componentName}.vue`
				if (frappeUIModules[modulePath]) {
					rawTemplate = frappeUIModules[modulePath]
				}
			}
		} catch (error) {
			console.error(`Error loading component template ${componentName}:`, error)
			return ""
		}
	} else {
		const modulePath = `/src/components/AppLayout/${componentName}.vue`
		if (studioModules[modulePath]) {
			rawTemplate = studioModules[modulePath]
		}
	}

	const template = rawTemplate || ""
	if (template) {
		templateCache.set(componentName, template)
	}
	return template
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

export { getComponentProps, getComponentTemplate, getComponentSlots }
