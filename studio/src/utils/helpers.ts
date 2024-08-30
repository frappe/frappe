import { reactive } from "vue"
import Block from "./block"
import getBlockTemplate from "./blockTemplate"

function getBlockInstance(options: Partial<BlockOptions>): Block {
	if (typeof options === "string") {
		options = JSON.parse(options)
	}
	return reactive(new Block(options))
}

function getComponentBlock(componentName: string) {
	return getBlockInstance({ componentName: componentName })
}

function getRootBlock(): Block {
	return getBlockInstance(getBlockTemplate("body"))
}

function getBlockCopy(block: BlockOptions | Block): Block {
	const b = JSON.parse(JSON.stringify(block))
	return getBlockInstance(b)
}

function numberToPx(number: number, round: boolean = true): string {
	/* appends 'px' to number with optional rounding */
	number = round ? Math.round(number) : number;
	return `${number}px`;
}

function kebabToCamelCase(str: string) {
	// convert border-color to borderColor
	return str.replace(/-([a-z])/g, function (g) {
		return g[1].toUpperCase();
	});
}

export {
	getBlockInstance,
	getComponentBlock,
	getRootBlock,
	getBlockCopy,
	numberToPx,
	kebabToCamelCase,
}
