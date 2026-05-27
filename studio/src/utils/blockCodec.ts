import { load as yamlLoad } from "js-yaml"

/**
 * Expand a compact YAML node (name/style/c/props...) into Studio block format
 * (componentName/baseStyles/children/componentProps...).
 * Mirrors BlockCodec.expand() in studio/ai_block_codec.py.
 */
export function expandBlock(node: Record<string, any>): Record<string, any> {
	const block: Record<string, any> = {
		componentName: node.name ?? "container",
		baseStyles: node.style ?? {},
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
 * Returns null if the buffer is not yet valid YAML or lacks a `name` key.
 */
export function tryParseYamlBlock(buffer: string): Record<string, any> | null {
	if (!buffer.trim()) return null
	try {
		const node = yamlLoad(buffer)
		if (!node || typeof node !== "object" || !("name" in node)) return null
		return expandBlock(node as Record<string, any>)
	} catch {
		return null
	}
}
