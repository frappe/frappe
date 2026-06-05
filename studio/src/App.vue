<template>
	<div class="h-full">
		<FrappeUIProvider>
			<router-view v-slot="{ Component }">
				<keep-alive>
					<component :is="Component" />
				</keep-alive>
			</router-view>
		</FrappeUIProvider>
	</div>
</template>

<script setup lang="ts">
import { FrappeUIProvider } from "frappe-ui"
</script>
