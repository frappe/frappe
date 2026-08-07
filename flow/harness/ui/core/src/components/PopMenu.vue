<template>
	<template v-if="open">
		<span class="fixed inset-0 z-10" @click="emit('close')" />
		<span
			class="absolute bottom-full z-20 mb-2.5 flex flex-col gap-0.5 rounded-[10px] border border-outline-gray-2 bg-surface-white p-1 shadow-xl"
			:class="align === 'right' ? 'right-0' : 'left-0'"
			:style="{ width: width + 'px' }"
		>
			<slot />
		</span>
	</template>
</template>

<script setup>
import { onBeforeUnmount, watch } from "vue"

const props = defineProps({
	open: { type: Boolean, default: false },
	align: { type: String, default: "left" },
	width: { type: Number, default: 244 },
})
const emit = defineEmits(["close"])

function onEscape(e) {
	if (e.key === "Escape") emit("close")
}
watch(
	() => props.open,
	(open) => {
		if (open) window.addEventListener("keydown", onEscape)
		else window.removeEventListener("keydown", onEscape)
	},
	{ immediate: true }, // a menu mounted already-open still gets its listener
)
onBeforeUnmount(() => window.removeEventListener("keydown", onEscape))
</script>
