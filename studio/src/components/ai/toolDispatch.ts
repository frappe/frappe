import type Block from "@/utils/block"
import type { styleProperty } from "@/utils/block"
import type { StyleValue } from "@/types"

interface Canvas {
	findBlock: (componentId: string) => Block | null
}

/**
 * Applies the agent's client-side tool operations to the canvas block tree using
 * Studio's block API. Each op the backend emits in `ai_chat_tool_batch` maps to a
 * setter here. Reads the same field names the tools declare (see studio/ai/agent/tools).
 */
export class ToolDispatcher {
	constructor(private readonly getCanvas: () => Canvas | null) {}

	applyToolBatch(operations: Array<{ tool_name: string; args: Record<string, any> }>) {
		for (const op of operations) {
			try {
				this.applyToolOperation(op.tool_name, op.args)
			} catch (e) {
				console.warn(`[AI agent] tool "${op.tool_name}" failed:`, e)
			}
		}
	}

	applyToolOperation(toolName: string, args: Record<string, any>) {
		switch (toolName) {
			case "update_block":
				return this.updateBlock(args)
		}
	}

	private updateBlock(args: Record<string, any>) {
		const block = this.getCanvas()?.findBlock(args.component_id)
		if (!block) return
		if (args.props) {
			for (const [key, value] of Object.entries(args.props)) block.setProp(key, value)
		}
		if (args.style) {
			for (const [key, value] of Object.entries(args.style)) {
				block.setBaseStyle(key as styleProperty, value as StyleValue)
			}
		}
		if (args.rstyle) Object.assign(block.rawStyles, args.rstyle)
		if (args.mstyle) Object.assign(block.mobileStyles, args.mstyle)
		if (args.tstyle) Object.assign(block.tabletStyles, args.tstyle)
		if (args.label !== undefined) block.blockName = args.label
	}
}
