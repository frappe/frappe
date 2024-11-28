<template>
	<div>
		<router-view v-slot="{ Component }">
			<keep-alive>
				<component :is="Component" />
			</keep-alive>
		</router-view>

		<Dialogs></Dialogs>
		<Toasts />
	</div>
</template>

<script setup lang="ts">
import { Dialogs, Toasts } from "frappe-ui"
</script>
