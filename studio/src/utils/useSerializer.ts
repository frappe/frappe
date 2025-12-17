import { reactive, toRaw, h } from "vue"
import Block from "./block"
import getBlockTemplate from "@/utils/blockTemplate"
import { deepCloneObject } from "@/utils/helpers"
import { FUNCTION_STRING_REGEX } from "@/utils/constants"

import type { ObjectLiteral, BlockOptions } from "@/types"
import useCodeStore from "@/stores/codeStore"

/**
 * Serialization and Deserialization utilities for Blocks and Objects
*/
export const useSerializer = () => {
	function isJSONString(str: string) {
		try {
			jsonToJs(str)
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

	const jsonReviver = (_key: string, value: any) => {
		const codeStore = useCodeStore()
		const registeredComponents = window.__APP_COMPONENTS__ || {}
		if (typeof value === "string") {
			const trimmed = value.trim()
			const isFunctionString = FUNCTION_STRING_REGEX.test(trimmed)

			if (isFunctionString) {
				try {
					// provide access to render function & frappeUI lib for editing props
					const fn = new Function(
						"h",
						...Object.keys(registeredComponents),
						...Object.keys(codeStore.globalExecutionContext),
						`return (${value})`
					)
					return fn(h, ...Object.values(registeredComponents), ...Object.values(codeStore.globalExecutionContext))
				} catch (e) {
					return value
				}
			}
		}
		return value
	}

	function jsonToJs(json: string): any {
		return JSON.parse(json, jsonReviver)
	}

	function copyObject<T>(obj: T) {
		if (!obj) return {}
		return jsonToJs(jsToJson(obj))
	}

	function parseObjectString(jsString: string) {
		const codeStore = useCodeStore()
		const registeredComponents = window.__APP_COMPONENTS__ || {}
		try {
			// Quote dynamic values before parsing
			const processedString = quoteDynamicValues(jsString)
			const fn = new Function(
				"h",
				...Object.keys(registeredComponents),
				...Object.keys(codeStore.globalExecutionContext),
				`return (${processedString})`
			)
			return fn(h, ...Object.values(registeredComponents), ...Object.values(codeStore.globalExecutionContext))
		} catch (e) {
			throw e
		}
	}

	function quoteDynamicValues(str: string): string {
		// Match {{ ... }} that is not already quoted (not preceded by " or ')
		// This regex looks for {{ ... }} patterns that are not surrounded by quotes
		return str.replace(/:\s*({{[^}]+}})\s*([,}\n\r])/g, ': "$1"$2')
	}

	function getBlockString(block: BlockOptions | Block): string {
		return jsToJson(getBlockCopyWithoutParent(block))
	}

	function getBlockObjectCopy(block: BlockOptions | Block): BlockOptions {
		return jsonToJs(getBlockString(block))
	}

	function getBlockInstance(options: BlockOptions | string, retainId = true): Block {
		if (typeof options === "string") {
			options = jsonToJs(options) as BlockOptions
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

	function getComponentBlock(componentName: string, isStudioComponent: boolean = false) {
		return getBlockInstance({ componentName: componentName, isStudioComponent: isStudioComponent, blockName: componentName })
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

	return {
		isJSONString,
		jsToJson,
		jsonReplacer,
		jsonToJs,
		jsonReviver,
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
}