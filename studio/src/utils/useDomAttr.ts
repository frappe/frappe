import { ref, watch, onMounted, onBeforeUnmount, unref } from "vue"

type MaybeRef<T> = T | { value: T }

export function useDomAttr(
	target: MaybeRef<HTMLElement | null>,
	attrName: string,
	options: {
		immediate?: boolean
		transform?: (value: string | null) => any
	} = {},
) {
	const { immediate = true, transform = (v) => v } = options

	const value = ref<any>(null)
	let observer: MutationObserver | null = null

	const read = () => {
		const el = unref(target as HTMLElement)
		if (!el) return
		value.value = transform(el.getAttribute(attrName))
	}

	onMounted(() => {
		const el = unref(target as HTMLElement)
		if (!el) return

		if (immediate) read()

		observer = new MutationObserver((mutations) => {
			for (const m of mutations) {
				if (m.type === "attributes" && m.attributeName === attrName) {
					read()
				}
			}
		})

		observer.observe(el, {
			attributes: true,
			attributeFilter: [attrName],
		})
	})

	onBeforeUnmount(() => {
		observer?.disconnect()
		observer = null
	})

	return value
}
