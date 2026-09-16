<template>
	<FlowPage v-if="boot" :boot="boot" />
	<div v-else class="flex h-full items-center justify-center bg-surface-base px-6 text-center">
		<div v-if="error" class="max-w-md">
			<div class="text-lg font-medium text-ink-gray-9">Flow could not start</div>
			<div class="mt-2 text-sm text-ink-gray-6">{{ error }}</div>
			<a href="/app" class="mt-4 inline-block text-sm font-medium text-ink-gray-8 underline"
				>Open the Desk</a
			>
		</div>
		<LoadingIndicator v-else class="h-5 w-5 text-ink-gray-5" />
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { LoadingIndicator } from "frappe-ui";

import { loadBoot } from "./boot.js";
import FlowPage from "./chat/FlowPage.vue";

const boot = ref(null);
const error = ref("");

onMounted(async () => {
	try {
		boot.value = await loadBoot();
	} catch (err) {
		error.value = err?.message ?? "Could not load the page.";
	}
});
</script>
