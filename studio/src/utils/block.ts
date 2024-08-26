import { BlockOptions, BlockStyleMap } from "@/types"
import { clamp } from "@vueuse/core"
import { reactive, CSSProperties } from 'vue'

export type styleProperty = keyof CSSProperties;
class Block implements BlockOptions {
	componentId: string
	componentName: string
	children: BlockOptions[]
	parentBlock: Block | null
	baseStyles: BlockStyleMap

	constructor(options: BlockOptions) {
		this.componentName = options.componentName
		this.baseStyles = reactive(options.baseStyles || {})

		// generate ID
		if (!options.componentId) {
			this.componentId = this.generateComponentId()
		} else {
			this.componentId = options.componentId
		}

		// set up hierarchy
		this.parentBlock = options.parentBlock || null
		this.children = (options.children || []).map((child: BlockOptions) => {
			child.parentBlock = this;
			return reactive(new Block(child))
		})
	}

	generateComponentId(componentName?: string | null): string {
		return `${componentName || this.componentName}-${Math.random().toString(36).substring(2, 9)}`
	}

	addChild(child: BlockOptions, index?: number | null) {
		child.parentBlock = this
		if (index === undefined || index === null) {
			index = this.children.length
		}
		index = clamp(index, 0, this.children.length)

		this.children.splice(index, 0, child)
		return child
	}

	getStyles(): BlockStyleMap {
		return { ...this.baseStyles }
	}

	getStyle(style: styleProperty) {
		return this.baseStyles[style]
	}

	isRoot() {
		return this.componentId === "root";
	}
}

export default Block