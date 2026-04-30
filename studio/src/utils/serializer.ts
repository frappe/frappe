import { reactive, toRaw } from "vue"
import Block from "./block"
import getBlockTemplate from "@/utils/blockTemplate"
import { deepCloneObject } from "@/utils/helpers"

import type { ObjectLiteral, BlockOptions } from "@/types"

/**
 * Serialization and Deserialization utilities for Blocks and Objects
 */
function isJSONString(str: string) {
	try {
		JSON.parse(str)
	} catch (e) {
		return false
	}
	return true
}

const jsonReplacer = (_key: string, value: any) => {
	// Preserve functions by converting them to strings
	if (typeof value === "function") {
		return value.toString()
	}
	// Handle circular references
	if (typeof value === "object" && value !== null) {
		if (value instanceof Set) {
			return [...value]
		}
		if (value instanceof Map) {
			return Object.fromEntries(value.entries())
		}
	}
	return value
}

function jsToJson(obj: ObjectLiteral): string {
	return JSON.stringify(obj, jsonReplacer, 2)
}

function copyObject<T>(obj: T) {
	if (!obj) return {}
	return JSON.parse(jsToJson(obj))
}

function parseObjectString(jsString: string) {
	try {
		const processedString = quoteDynamicValues(jsString)
		const obj = new Function(`return (${processedString})`)()
		return stringifyFunctions(obj, jsString)
	} catch (e) {
		throw e
	}
}

function stringifyFunctions(obj: any, originalSource: string): any {
	if (obj === null || obj === undefined) {
		return obj
	}

	if (typeof obj === "function") {
		return obj.toString()
	}

	if (Array.isArray(obj)) {
		return obj.map((item) => stringifyFunctions(item, originalSource))
	}

	if (typeof obj === "object") {
		const result: Record<string, any> = {}
		for (const [key, value] of Object.entries(obj)) {
			result[key] = stringifyFunctions(value, originalSource)
		}
		return result
	}

	return obj
}

function quoteDynamicValues(str: string): string {
	// Match {{ ... }} that is not already quoted (not preceded by quotes)
	// Use backticks so that inner single/double quotes don't break
	return str.replace(/:\s*({{[^}]+}})\s*([,}\n\r])/g, ': `$1`$2')
}

function getBlockString(block: BlockOptions | Block): string {
	return jsToJson(getBlockCopyWithoutParent(block))
}

function getBlockObjectCopy(block: BlockOptions | Block): BlockOptions {
	return JSON.parse(getBlockString(block))
}

function getBlockInstance(options: BlockOptions | string, retainId = true): Block {
	if (typeof options === "string") {
		options = JSON.parse(options) as BlockOptions
	}
	if (!retainId) {
		const deleteComponentId = (block: BlockOptions) => {
			delete block.componentId
			for (let child of block.children || []) {
				deleteComponentId(child)
			}

			// clear componentId of slot children
			for (let slot of Object.values(block.componentSlots || {})) {
				if (Array.isArray(slot.slotContent)) {
					for (let child of slot.slotContent) {
						deleteComponentId(child)
					}
				}
			}
		}

		const deleteSlotId = (block: BlockOptions) => {
			for (let slot of Object.values(block.componentSlots || {})) {
				delete slot.slotId
			}
		}

		deleteComponentId(options)
		deleteSlotId(options)
	}
	return reactive(new Block(options))
}

function getComponentBlock(componentName: string, isStudioComponent: boolean = false, isCustomVueComponent: boolean = false) {
	return getBlockInstance({
		componentName: componentName,
		isStudioComponent: isStudioComponent,
		isCustomVueComponent: isCustomVueComponent,
	})
}

function getRootBlock(): Block {
	return getBlockInstance(getBlockTemplate("body"))
}

function getBlockCopy(block: BlockOptions | Block, retainId = false): Block {
	// remove parent block reference as JSON doesn't accept circular references
	const b = copyObject(getBlockCopyWithoutParent(block))
	return getBlockInstance(b, retainId)
}

function getBlockCopyWithoutParent(block: BlockOptions | Block) {
	const rawBlock = toRaw(block)
	const blockCopy = deepCloneObject(rawBlock, ["parentBlock"]) as BlockOptions
	delete blockCopy.parentBlock
	delete blockCopy.repeaterDataItem
	delete blockCopy.componentContext

	blockCopy.children = blockCopy.children?.map((child) => getBlockCopyWithoutParent(child))

	// remove parentBlock reference for slot children
	for (const slot of Object.values(blockCopy.componentSlots || {})) {
		if (Array.isArray(slot.slotContent)) {
			slot.slotContent = slot.slotContent.map((child) => getBlockCopyWithoutParent(child))
		}
	}

	return blockCopy
}

export {
	isJSONString,
	jsToJson,
	jsonReplacer,
	copyObject,
	parseObjectString,
	quoteDynamicValues,
	// block serialization/deserialization
	getBlockString,
	getBlockObjectCopy,
	getBlockInstance,
	getComponentBlock,
	getRootBlock,
	getBlockCopy,
	getBlockCopyWithoutParent,
}
