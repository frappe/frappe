type StyleValue = string | number | null | undefined

interface BlockStyleMap {
	[key: string]: StyleValue
}

interface BlockOptions {
	componentId: string
	componentName: string
	children: BlockOptions[]
	baseStyles: BlockStyleMap
}