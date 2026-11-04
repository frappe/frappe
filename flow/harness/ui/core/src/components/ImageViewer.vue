<template>
	<!-- frappe-ui's Dialog portals where its host keeps overlays (inside an island's shadow root),
	     and brings the overlay, Escape, the focus trap and focus return -->
	<Dialog open bare size="5xl" @update:open="(open) => open || emit('close')">
		<Dialog.Title class="sr-only">{{ alt || "Image" }}</Dialog.Title>
		<div class="relative flex items-center justify-center p-2">
			<img :src="src" :alt="alt" class="max-h-[calc(100vh-8rem)] max-w-full rounded-5 object-contain" />
			<Button variant="subtle" icon="lucide-x" title="Close" class="absolute right-4 top-4" @click="emit('close')" />
		</div>
	</Dialog>
</template>

<script setup>
import { Button } from "frappe-ui/src/components/Button"
import { Dialog } from "frappe-ui/src/components/Dialog"

defineProps({
	src: { type: String, required: true },
	alt: { type: String, default: "" },
})
const emit = defineEmits(["close"])
</script>
