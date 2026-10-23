import { onScopeDispose, ref, watch } from "vue"

// A ref that trails `source` by `delay` ms — one timer, latest value wins.
export function useDebouncedValue(source, delay = 150) {
	const out = ref(source.value)
	let timer
	watch(source, (value) => {
		clearTimeout(timer)
		timer = setTimeout(() => (out.value = value), delay)
	})
	onScopeDispose(() => clearTimeout(timer))
	return out
}
