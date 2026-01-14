export type StudioPageWatcher = {
	source: string,
	script: string,
	immediate: boolean,
	deep: boolean,
	debounce?: number,
	parent?: string,
	name?: string,
}