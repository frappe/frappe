import type Block from "@/utils/block"
import type { styleProperty } from "@/utils/block"
import type { BlockOptions, StyleValue } from "@/types"
import { expandBlock } from "@/utils/blockCodec"
import { getBlockCopyWithoutParent } from "@/utils/serializer"

interface Canvas {
	findBlock: (componentId: string) => Block | null
}

export interface DispatchContext {
	getCanvas: () => Canvas | null
	setRootBlock: (block: BlockOptions) => void
}

/**
 * Applies the agent's client-side tool operations to the canvas block tree using
 * Studio's block API. Each op the backend emits in `ai_chat_tool_batch` maps to a
 * setter here. Reads the same field names the tools declare (see studio/ai/agent/tools).
 */
export class ToolDispatcher {
	constructor(private readonly ctx: DispatchContext) {}

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
			case "generate_page":
				return this.ctx.setRootBlock(args.block as BlockOptions)
			case "update_block":
				return this.updateOne(args.component_id, args)
			case "update_blocks":
				return this.updateMany(args)
			case "add_block":
				return this.addBlock(args)
			case "remove_block":
				return this.removeBlock(args)
			case "move_block":
				return this.moveBlock(args)
		}
	}

	private updateOne(componentId: string, args: Record<string, any>) {
		const block = this.ctx.getCanvas()?.findBlock(componentId)
		if (block) this.applyBlockUpdate(block, args)
	}

	private updateMany(args: Record<string, any>) {
		// Per-block mode wins over uniform mode (matches the tool contract).
		if (Array.isArray(args.patches)) {
			for (const patch of args.patches as Record<string, any>[]) this.updateOne(patch.component_id, patch)
			return
		}
		for (const id of (args.component_ids as string[]) || []) this.updateOne(id, args)
	}

	/** Merge one block's worth of changes. Shared by update_block and update_blocks so
	 * the two can never drift. Reads the same field names the tools declare. */
	private applyBlockUpdate(block: Block, args: Record<string, any>) {
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

	private addBlock(args: Record<string, any>) {
		const parent = this.ctx.getCanvas()?.findBlock(args.parent_component_id)
		if (!parent) return
		const options = expandBlock(args.block || {})
		// The server assigned the id (echoed in args.component_id) so client and server agree.
		if (args.component_id) options.componentId = args.component_id
		const sibling = args.after_component_id
			? parent.children?.find((c) => c.componentId === args.after_component_id)
			: null
		if (sibling) {
			parent.addChildAfter(options, sibling)
			return
		}
		parent.addChild(options, typeof args.index === "number" ? args.index : null)
	}

	private removeBlock(args: Record<string, any>) {
		const block = this.ctx.getCanvas()?.findBlock(args.component_id)
		block?.getParentBlock()?.removeChild(block)
	}

	private moveBlock(args: Record<string, any>) {
		const canvas = this.ctx.getCanvas()
		const block = canvas?.findBlock(args.component_id)
		const newParent = canvas?.findBlock(args.new_parent_component_id)
		if (!block || !newParent) return
		const options = getBlockCopyWithoutParent(block)
		block.getParentBlock()?.removeChild(block)
		const sibling = args.after_component_id
			? newParent.children?.find((c) => c.componentId === args.after_component_id)
			: null
		if (sibling) {
			newParent.addChildAfter(options, sibling)
			return
		}
		newParent.addChild(options, typeof args.index === "number" ? args.index : null)
	}
}
