<template>
	<div>
		<router-view v-slot="{ Component }">
			<keep-alive>
				<component :is="Component" />
			</keep-alive>
		</router-view>

		<Toaster :visible-toasts="2" position="bottom-right" richColors />
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