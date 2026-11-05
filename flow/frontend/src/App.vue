<template>
	<div class="h-full">
		<FlowPage v-if="boot" :boot="boot" />
		<div
			v-else
			class="flex h-full items-center justify-center bg-surface-base px-6 text-center"
		>
			<div v-if="error" class="max-w-md">
				<div class="text-xl-medium text-ink-gray-9">Flow could not start</div>
				<div class="mt-2 text-base text-ink-gray-6">{{ error }}</div>
				<!-- in a panel the Desk is already the page around it -->
				<div v-if="panel" class="mt-4 flex justify-center gap-2">
					<Button label="Reload" variant="solid" @click="reload" />
					<Button label="Close" @click="emit('close')" />
				</div>
				<a
					v-else
					href="/desk"
					class="mt-4 inline-block text-base-medium text-ink-gray-8 underline"
					>Open the Desk</a
				>
			</div>
			<LoadingIndicator v-else class="h-5 w-5 text-ink-gray-5" />
		</div>
	</div>
</template>

<script setup>
import { onMounted, provide, ref } from "vue";
import { Button, LoadingIndicator } from "frappe-ui";

import { loadBoot } from "./boot.js";
import FlowPage from "./chat/FlowPage.vue";

// the island's props; see island.js
const props = defineProps({
	boot: { type: Object, default: null },
	panel: { type: String, default: null },
	path: { type: String, default: null },
});
const emit = defineEmits(["close", "navigate"]);
provide("flowHost", {
	close: () => emit("close"),
});

const boot = ref(null);
const reload = () => window.location.reload();
const error = ref("");

onMounted(async () => {
	try {
		boot.value = await loadBoot(props.boot);
	} catch (err) {
		error.value = err?.message ?? "Could not load the page.";
	}
});
</script>
