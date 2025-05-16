<template>
	<div class="h-full">
		<router-view />
		<Toaster :visible-toasts="2" position="bottom-right" richColors closeButton />
		<Dialogs></Dialogs>
	</div>
</template>

<script setup lang="ts">
import { Dialogs } from "frappe-ui"
import { Toaster } from "vue-sonner"
</script>

<style>
[id^="headlessui-dialog"] {
	@apply z-50;
}
</style>
