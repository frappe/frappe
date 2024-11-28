<template>
	<div>
		<router-view v-slot="{ Component }">
			<keep-alive>
				<component :is="Component" />
			</keep-alive>
		</router-view>

		<Dialogs></Dialogs>
		<Toaster :visible-toasts="2" position="bottom-right" richColors />
	</div>
</template>

<script setup lang="ts">
import { Toaster } from "vue-sonner"
</script>
