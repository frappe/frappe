<template>
	<Teleport to="body">
		<div
			class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6"
			role="dialog"
			aria-modal="true"
			:aria-label="alt || 'Image'"
			@click.self="emit('close')"
		>
			<img :src="src" :alt="alt" class="max-h-full max-w-full rounded-6 object-contain shadow-2xl" />
			<button
				ref="closeEl"
				class="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-full bg-white/15 text-white hover:bg-white/25"
				title="Close"
				@click="emit('close')"
			>
				<FeatherIcon name="x" class="h-4 w-4" />
			</button>
		</div>
	</Teleport>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

defineProps({
	src: { type: String, required: true },
	alt: { type: String, default: "" },
})
const emit = defineEmits(["close"])
const closeEl = ref(null)
let returnFocus = null

// capture phase: an open viewer owns Escape before the composer's global
// abort listener (and any focused element) can act on the same keypress
function onKey(event) {
	if (event.key !== "Escape") return
	event.preventDefault()
	event.stopPropagation()
	emit("close")
}

onMounted(() => {
	returnFocus = document.activeElement
	window.addEventListener("keydown", onKey, true)
	closeEl.value?.focus()
})
onBeforeUnmount(() => {
	window.removeEventListener("keydown", onKey, true)
	returnFocus?.focus?.()
})
</script>
