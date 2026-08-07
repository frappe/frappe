import { nextTick, ref, watch } from "vue"

// Arrow-key navigation shared by the palette lists (models, providers,
// commands). Owns the highlighted index, wrap-around movement, and keeping the
// active row scrolled into view; `listEl` goes on the scrolling container and
// `data-palette-active` on each row.
export function usePaletteNav(items, { onSelect, onEscape } = {}) {
	const activeIndex = ref(0)
	const listEl = ref(null)

	// the list reshapes as the user types — never leave the highlight past its end
	watch(items, (rows) => {
		if (activeIndex.value >= rows.length) activeIndex.value = 0
	})

	function move(delta) {
		const count = items.value.length
		if (!count) return
		activeIndex.value = (activeIndex.value + delta + count) % count
		nextTick(() => {
			listEl.value?.querySelector("[data-palette-active='true']")?.scrollIntoView({ block: "nearest" })
		})
	}

	function onKey(e) {
		if (e.key === "ArrowDown") {
			e.preventDefault()
			move(1)
		} else if (e.key === "ArrowUp") {
			e.preventDefault()
			move(-1)
		} else if (e.key === "Enter") {
			const row = items.value[activeIndex.value]
			if (!row) return
			e.preventDefault()
			onSelect?.(row)
		} else if (e.key === "Escape") {
			onEscape?.()
		}
	}

	return { activeIndex, listEl, move, onKey }
}
