<template>
	<div class="h-full">
		<FrappeUIProvider>
			<router-view v-slot="{ Component }">
				<keep-alive>
					<component :is="Component" />
				</keep-alive>
			</router-view>
		</FrappeUIProvider>

		<Toaster :visible-toasts="2" position="bottom-right" richColors closeButton />
	</div>
</template>

<script setup lang="ts">
import { FrappeUIProvider } from "frappe-ui"
import { Toaster } from "vue-sonner"
</script>
