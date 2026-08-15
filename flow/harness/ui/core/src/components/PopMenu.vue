<template>
	<template v-if="open">
		<span class="fixed inset-0 z-10" aria-hidden="true" @click="close" />
		<div
			ref="menuEl"
			role="menu"
			:aria-label="label"
			class="flow-pop-menu absolute z-20 flex flex-col gap-0.5 rounded-[10px] border border-outline-gray-2 bg-surface-white p-1 shadow-xl outline-none"
			:class="[
				align === 'right' ? 'right-0' : 'left-0',
				placement === 'bottom' ? 'top-full mt-2.5' : 'bottom-full mb-2.5',
			]"
			:style="{ width: width + 'px' }"
			@keydown="onKey"
		>
			<slot />
		</div>
	</template>
</template>

<script setup>
import { nextTick, ref, watch } from "vue"

import { nextNavigationIndex } from "../paletteNav.js"

const props = defineProps({
	open: { type: Boolean, default: false },
	align: { type: String, default: "left" },
	placement: { type: String, default: "top" },
	width: { type: Number, default: 244 },
	label: { type: String, default: "Menu" },
})
const emit = defineEmits(["close"])
const menuEl = ref(null)
let returnFocus = null

function items() {
	return [...(menuEl.value?.querySelectorAll("button:not(:disabled)") ?? [])]
}

function close() {
	emit("close")
	nextTick(() => returnFocus?.focus())
}

function onKey(event) {
	if (event.key === "Escape") {
		event.preventDefault()
		event.stopPropagation()
		close()
		return
	}
	const rows = items()
	const current = rows.indexOf(document.activeElement)
	if ((event.key === "Enter" || event.key === " ") && current !== -1) {
		event.preventDefault()
		event.stopPropagation()
		rows[current].click()
		return
	}
	const nextIndex = nextNavigationIndex(current, rows.length, event.key)
	if (nextIndex === null) return
	event.preventDefault()
	event.stopPropagation()
	rows[nextIndex].focus()
	rows[nextIndex].scrollIntoView({ block: "nearest" })
}

watch(
	() => props.open,
	async (open, wasOpen) => {
		if (open) {
			returnFocus = document.activeElement
			await nextTick()
			const rows = items()
			const selected = rows.find(
				(row) => row.getAttribute("aria-checked") === "true" || row.dataset.menuSelected === "true",
			)
			const firstItem = selected ?? rows[0]
			firstItem?.focus({ preventScroll: true })
		} else if (wasOpen) {
			await nextTick()
			if (document.activeElement === document.body) returnFocus?.focus()
		}
	},
	{ immediate: true }, // a menu mounted already-open still receives initial focus
)
</script>

<style scoped>
.flow-pop-menu :deep(button:focus-visible),
.flow-pop-menu :deep([role^="menuitem"]:focus-visible) {
	background: var(--surface-gray-2);
	outline: none;
}
</style>
