export type VuePropType = {
	name: 'String' | 'Number' | 'Boolean' | 'Array' | 'Object' | 'Function'
	[key: string]: any
}

export type VuePropDefaultType = string | number | boolean | undefined
export type VuePropDefault = VuePropDefaultType | (() => VuePropDefaultType)

export type VueProp = {
	type: VuePropType | VuePropType[]
	default: VuePropDefault
	required: boolean
}