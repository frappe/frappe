<template>
	<div class="h-full">
		<Toaster :visible-toasts="2" position="bottom-right" richColors closeButton />
		<FrappeUIProvider>
			<router-view />
		</FrappeUIProvider>
	</div>
</template>

<script setup lang="ts">
import { FrappeUIProvider } from "frappe-ui"
import { Toaster } from "vue-sonner"
</script>
