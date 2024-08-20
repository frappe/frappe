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

export {
	getBlockInstance,
	getComponentBlock,
	getRootBlock,
	getBlockCopy
}
