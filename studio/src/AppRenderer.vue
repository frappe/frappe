<template>
	<div class="h-full">
		<FrappeUIProvider>
			<router-view />
		</FrappeUIProvider>
	</div>
</template>

<script setup lang="ts">
import { FrappeUIProvider } from "frappe-ui"
</script>
