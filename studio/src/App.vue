<template>
	<div>
		<router-view v-slot="{ Component }">
			<keep-alive>
				<component :is="Component" />
			</keep-alive>
		</router-view>

		<Dialogs></Dialogs>
	</div>
</template>

<script setup lang="ts">
import { Dialogs } from "frappe-ui"
</script>
