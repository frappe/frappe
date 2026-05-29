import { BlockOptions } from "@/types"
import { load as yamlLoad } from "js-yaml"

/**
 * Expand a compact YAML node (name/style/c/props...) into Studio block format
 * (componentName/baseStyles/children/componentProps...).
 * Mirrors BlockCodec.expand() in studio/ai/block_codec.py.
 */
export function expandBlock(node: Record<string, any>): BlockOptions {
	const block: BlockOptions = {
		componentName: node.name ?? "container",
		baseStyles: node.style ?? {},
		rawStyles: node.rstyle ?? {},
		componentProps: node.props ?? {},
		componentSlots: node.slots ?? {},
		mobileStyles: node.mstyle ?? {},
		tabletStyles: node.tstyle ?? {},
		children: Array.isArray(node.c) ? node.c.map(expandBlock) : [],
	}

	if (node.id) block.componentId = node.id
	if (node.originalElement) block.originalElement = node.originalElement
	if (node.label) block.blockName = node.label

	return block
}

/**
 * Try to parse a partial YAML stream buffer into a Studio block.
 * On parse failure, walks backwards line by line dropping the trailing
 * incomplete line — fallback to handle mid-stream truncation and apostrophe-in-single-quote errors.
 */
export function tryParseYamlBlock(buffer: string): BlockOptions | null {
	if (!buffer.trim()) return null
	const parsed = getValidPartialYAML(buffer)
	if (!parsed || typeof parsed !== "object" || !("name" in parsed)) return null
	return expandBlock(parsed as Record<string, any>)
}

function getValidPartialYAML(text: string): unknown {
	try {
		return yamlLoad(text)
	} catch {
		const lines = text.split("\n")
		for (let i = lines.length - 1; i > 0; i--) {
			try {
				const result = yamlLoad(lines.slice(0, i).join("\n"))
				if (result) return result
			} catch {
				// keep trimming
			}
		}
		return null
	}
}
