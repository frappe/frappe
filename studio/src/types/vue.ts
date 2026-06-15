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
	condition?: (props: any) => boolean
}

export interface CustomVueComponentMeta {
	component_name: string
	frappe_app: string
	studio_app: string
	file_path: string
	studio_file_path: string
}