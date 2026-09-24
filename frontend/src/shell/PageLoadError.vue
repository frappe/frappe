<template>
	<div
		role="alert"
		class="flex h-full w-full flex-col items-center justify-center gap-2 p-8 text-center"
	>
		<p class="text-lg font-medium text-ink-gray-8">{{ __("Something went wrong") }}</p>
		<p class="text-sm text-ink-gray-6">{{ __("This page could not load.") }}</p>
		<Button class="mt-2" :label="__('Try again')" @click="retry" />
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { __ } from "@/i18n";

const props = defineProps<{ href: string }>();

// A full reload: the browser can keep a failed module fetch and fail an in-app retry again.
function retry() {
	const { pathname, search, hash } = window.location;
	// Assigning the current address with a hash only scrolls to the hash; it does not reload.
	if (props.href === pathname + search + hash) window.location.reload();
	else window.location.assign(props.href);
}
</script>
