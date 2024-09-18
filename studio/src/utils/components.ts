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
			propsConfig[propName] = {
				type: config.type?.name,
				default: config.default,
				inputType: getPropInputType(config.type?.name),
			}
		})
	}
	return propsConfig
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