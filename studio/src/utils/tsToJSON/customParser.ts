import { Context, StringType, ReferenceType, BaseType, SubNodeParser } from "ts-json-schema-generator"
import ts from "typescript"

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