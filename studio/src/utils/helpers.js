import { reactive } from "vue"

function getComponentCopy(component) {
	return JSON.parse(JSON.stringify(component))
}

function getBlockCopy(block) {
	if (typeof block === "string") {
		block = JSON.parse(block)
	}

	return reactive(...block)
}

export { getComponentCopy, getBlockCopy }
