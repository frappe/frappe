<template>
	<div class="h-full">
		<Toaster :visible-toasts="2" position="bottom-right" richColors closeButton />
		<FrappeUIProvider>
			<router-view />
		</FrappeUIProvider>
		<Dialogs></Dialogs>
	</div>
</template>

<script setup lang="ts">
import { Dialogs, FrappeUIProvider } from "frappe-ui"
import { Toaster } from "vue-sonner"
</script>
