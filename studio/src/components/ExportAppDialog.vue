<template>
	<Dialog v-model:open="showDialog" title="Export Settings" size="xl">
		<template #default>
			<AppExport @updated="showDialog = false" />
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Dialog } from "frappe-ui"
import AppExport from "@/components/Settings/AppExport.vue"

const showDialog = defineModel("showDialog", { type: Boolean, required: true })
</script>
