<!-- The shared dropdown shell for everything that floats above the composer:
     slash commands, model picker, thinking, providers. Overlay + panel +
     header; search is a slot so each surface stays a thin list. -->
<template>
	<div class="fixed inset-0 z-10" @click="emit('close')" />
	<section
		class="absolute bottom-[calc(100%+10px)] left-0 z-20 flex max-h-[min(500px,72vh)] w-full flex-col overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white shadow-[0_18px_50px_rgba(0,0,0,0.14)]"
	>
		<header class="flex h-11 flex-none items-center gap-2 border-b border-outline-gray-1 px-2">
			<button
				v-if="back"
				class="flex h-7 w-7 items-center justify-center rounded-md text-ink-gray-5 hover:bg-surface-gray-2"
				title="Back"
				@click="emit('back')"
			>
				<FeatherIcon name="arrow-left" class="h-3.5 w-3.5" />
			</button>
			<span class="min-w-0 truncate text-xs font-medium text-ink-gray-9" :class="back ? '' : 'pl-1'">
				{{ title }}
			</span>
			<span class="flex-1" />
			<slot name="actions" />
		</header>
		<slot name="search" />
		<slot />
	</section>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

defineProps({
	title: { type: String, required: true },
	back: { type: Boolean, default: false },
})
const emit = defineEmits(["close", "back"])

// Escape closes the panel wherever focus is — not only inside the composer
function onEscape(e) {
	if (e.key === "Escape") emit("close")
}
onMounted(() => window.addEventListener("keydown", onEscape))
onBeforeUnmount(() => window.removeEventListener("keydown", onEscape))
</script>
