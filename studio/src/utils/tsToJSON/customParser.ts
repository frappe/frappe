import {
	Context,
	StringType,
	ReferenceType,
	BaseType,
	SubNodeParser,
	ObjectType,
	UnionType,
} from "ts-json-schema-generator"
import ts from "typescript"

/*
Custom parser for complex types that are not supported by ts-json-schema-generator.
Reference: https://github.com/vega/ts-json-schema-generator#custom-parsing
*/
export class SVGElementParser implements SubNodeParser {
	supportsNode(node: ts.Node): boolean {
		if (ts.isTypeReferenceNode(node) && node.typeName.getText() === "SVGElement") {
			return true
		}
		return false
	}

	createType(node: ts.Node, context: Context, reference?: ReferenceType): BaseType {
		return new StringType() // treat SVGElement as a string
	}
}

export class VueComponentParser implements SubNodeParser {
	supportsNode(node: ts.Node): boolean {
		if (ts.isTypeReferenceNode(node)) {
			const typeName = node.typeName.getText()
			return typeName === "Component" || typeName === "ComponentPublicInstance"
		}
		return false
	}

	createType(node: ts.Node, context: Context, reference?: ReferenceType): BaseType {
		// treat Component and ComponentPublicInstance as String
		return new StringType()
	}
}

export class RouteLocationParser implements SubNodeParser {
	supportsNode(node: ts.Node): boolean {
		if (ts.isTypeReferenceNode(node)) {
			const typeName = node.typeName.getText()
			return (
				typeName === "RouteLocation" ||
				typeName === "RouteLocationNormalized" ||
				typeName === "RouteLocationRaw"
			)
		}
		return false
	}

	createType(node: ts.Node, context: Context, reference?: ReferenceType): BaseType {
		// treat RouteLocation, RouteLocationNormalized and RouteLocationRaw as a string or an object
		return new UnionType([new StringType(), new ObjectType("RouteLocation", [], [], true)])
	}
}

export class HTMLElementParser implements SubNodeParser {
	supportsNode(node: ts.Node): boolean {
		if (ts.isTypeReferenceNode(node)) {
			const typeName = node.typeName.getText()
			return typeName === "HTMLElement" || typeName === "Element" || typeName === "Node"
		}
		return false
	}

	createType(node: ts.Node, context: Context, reference?: ReferenceType): BaseType {
		// treat DOM element types as strings to avoid expanding the entire DOM API
		return new StringType()
	}
}

export class FunctionTypeParser implements SubNodeParser {
	supportsNode(node: ts.Node): boolean {
		return ts.isFunctionTypeNode(node)
	}

	createType(node: ts.Node, context: Context, reference?: ReferenceType): BaseType {
		// treat function types (e.g. (event: MouseEvent) => void) as plain objects
		// to avoid expanding function parameters into namedArgs structures
		return new ObjectType("function", [], [], true)
	}
}

export class SlotsParser implements SubNodeParser {
	supportsNode(node: ts.Node): boolean {
		if (ts.isTypeReferenceNode(node)) {
			const typeName = node.typeName.getText()
			return typeName.endsWith("Slots")
		}
		return false
	}

	createType(node: ts.Node, context: Context, reference?: ReferenceType): BaseType {
		// treat slot types (e.g. ComboboxItemSlots, DropdownSlots) as plain objects
		// to avoid deeply expanding Vue slot function signatures
		return new ObjectType("slots-object", [], [], true)
	}
}
