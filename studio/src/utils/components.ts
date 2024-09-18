import components from "@/data/components"

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
		Object.entries(props).forEach(([propName, config]) => {
			const propType = getPropType(config.type)
			propsConfig[propName] = {
				type: propType,
				default: config.default,
				inputType: getPropInputType(propType),
			}
		})
	}
	return propsConfig
}

function getPropType(propType: object) {
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

export {
	getComponentProps,
}