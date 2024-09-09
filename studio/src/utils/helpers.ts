import { reactive, toRaw } from "vue"
import Block from "./block"
import getBlockTemplate from "./blockTemplate"

function getBlockInstance(options: BlockOptions, retainId = true): Block {
	if (typeof options === "string") {
		options = JSON.parse(options)
	}
	if (!retainId) {
		const deleteComponentId = (block: BlockOptions) => {
			delete block.componentId
			for (let child of block.children || []) {
				deleteComponentId(child)
			}
		}
		deleteComponentId(options)
	}
	return reactive(new Block(options))
}

function getComponentBlock(componentName: string) {
	return getBlockInstance({ componentName: componentName })
}

function getRootBlock(): Block {
	return getBlockInstance(getBlockTemplate("body"))
}

function getBlockCopy(block: BlockOptions | Block, retainId = false): Block {
	// remove parent block reference as JSON doesn't accept circular references
	const blockString = JSON.stringify(getBlockCopyWithoutParent(block))
	const b = JSON.parse(blockString)
	return getBlockInstance(b, retainId)
}

function getBlockCopyWithoutParent(block: BlockOptions | Block): BlockOptions {
	const blockCopy = { ...toRaw(block) }
	blockCopy.children = blockCopy.children?.map((child) => getBlockCopyWithoutParent(child))
	delete blockCopy.parentBlock
	return blockCopy
}

function numberToPx(number: number, round: boolean = true): string {
	/* appends 'px' to number with optional rounding */
	number = round ? Math.round(number) : number;
	return `${number}px`;
}

function pxToNumber(px: string | number | null | undefined): number {
	if (!px) return 0
	if (typeof px === "number") return px

	const number = Number(px.replace("px", ""))
	if (isNaN(number)) return 0
	return number
}

function kebabToCamelCase(str: string) {
	// convert border-color to borderColor
	return str.replace(/-([a-z])/g, function (g) {
		return g[1].toUpperCase();
	});
}

function copy<T>(obj: T) {
	if (!obj) return {}
	return JSON.parse(JSON.stringify(obj))
}

function areObjectsEqual(obj1: any, obj2: any): boolean {
	const keys1 = Object.keys(obj1)
	const keys2 = Object.keys(obj2)

	if (keys1.length !== keys2.length) return false

	for (const key of keys1) {
		if (!obj2.hasOwnProperty(key)) return false

		if (typeof obj1[key] === "object" && typeof obj2[key] === "object") {
			if (!areObjectsEqual(obj1[key], obj2[key])) return false
		} else {
			if (obj1[key] !== obj2[key]) return false
		}
	}

	return true
}

export {
	getBlockInstance,
	getComponentBlock,
	getRootBlock,
	getBlockCopy,
	getBlockCopyWithoutParent,
	numberToPx,
	pxToNumber,
	kebabToCamelCase,
	copy,
	areObjectsEqual,
}
