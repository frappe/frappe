import {
	Context,
	StringType,
	ReferenceType,
	BaseType,
	SubNodeParser,
	ObjectType,
	ObjectProperty,
	UnionType,
	NumberType,
	BooleanType,
	ArrayType,
	AnyType,
	NodeParser,
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
				typeName === "RouteLocationRaw" ||
				typeName === "RouteDestination" ||
				typeName === "RouteLocationObject"
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

// frappe-ui derives some public props from runtime prop objects:
// `ExtractPublicPropTypes<typeof buttonProps>`. Read the prop object literal instead.
export class RuntimePropsParser implements SubNodeParser {
	constructor(
		private typeChecker: ts.TypeChecker,
		private childNodeParser: NodeParser,
	) {}

	supportsNode(node: ts.Node): boolean {
		return (
			ts.isTypeReferenceNode(node) &&
			["ExtractPublicPropTypes", "ExtractPropTypes"].includes(node.typeName.getText()) &&
			Boolean(node.typeArguments?.length && ts.isTypeQueryNode(node.typeArguments[0]))
		)
	}

	createType(node: ts.TypeReferenceNode, context: Context): BaseType {
		const query = node.typeArguments![0] as ts.TypeQueryNode
		const propsObject = this.resolveObjectLiteral(query.exprName)
		if (!propsObject) throw new Error(`Cannot resolve runtime props for ${node.getText()}`)

		const properties = propsObject.properties.flatMap((property) => {
			if (!ts.isPropertyAssignment(property) && !ts.isShorthandPropertyAssignment(property)) return []
			const definition = ts.isPropertyAssignment(property)
				? property.initializer
				: property.name
			return [
				new ObjectProperty(
					property.name.getText(),
					this.propType(definition, context),
					this.isRequired(definition),
				),
			]
		})
		return new ObjectType(`runtime-props-${query.exprName.getText()}`, [], properties, false)
	}

	private resolveObjectLiteral(node: ts.Node | undefined): ts.ObjectLiteralExpression | undefined {
		while (node && (ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isParenthesizedExpression(node))) {
			node = node.expression
		}
		if (!node) return undefined
		if (ts.isObjectLiteralExpression(node)) return node
		if (ts.isIdentifier(node) || ts.isQualifiedName(node)) {
			let symbol = this.typeChecker.getSymbolAtLocation(node)
			if (symbol && symbol.flags & ts.SymbolFlags.Alias) symbol = this.typeChecker.getAliasedSymbol(symbol)
			const declaration = symbol?.valueDeclaration
			if (declaration && ts.isVariableDeclaration(declaration)) {
				return this.resolveObjectLiteral(declaration.initializer)
			}
		}
		return undefined
	}

	private option(definition: ts.Node, name: string): ts.Expression | undefined {
		const options = this.resolveObjectLiteral(definition)
		if (!options) return definition as ts.Expression
		const option = options.properties.find((p) => p.name?.getText() === name)
		return option && ts.isPropertyAssignment(option) ? option.initializer : undefined
	}

	private isRequired(definition: ts.Node): boolean {
		const options = this.resolveObjectLiteral(definition)
		return Boolean(options && this.option(definition, "required")?.kind === ts.SyntaxKind.TrueKeyword)
	}

	private propType(definition: ts.Node, context: Context): BaseType {
		const type = this.option(definition, "type")
		if (!type) return new AnyType()
		if (ts.isAsExpression(type) && ts.isTypeReferenceNode(type.type) && type.type.typeArguments?.length) {
			return this.childNodeParser.createType(type.type.typeArguments[0], context)
		}
		if (ts.isArrayLiteralExpression(type)) {
			return new UnionType(type.elements.map((element) => constructorType(element.getText())))
		}
		return constructorType(type.getText())
	}
}

function constructorType(name: string): BaseType {
	switch (name) {
		case "String":
			return new StringType()
		case "Number":
			return new NumberType()
		case "Boolean":
			return new BooleanType()
		case "Array":
			return new ArrayType(new AnyType())
		case "Object":
			return new ObjectType("object", [], [], true)
		case "Function":
			return new ObjectType("function", [], [], true)
		default:
			return new AnyType()
	}
}
