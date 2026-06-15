<template>
	<Dialog v-model="showDialog" title="Export Settings" size="xl">
		<template #default>
			<AppExportSettings
				v-model:enableExport="enableExport"
				v-model:targetApp="targetApp"
				:app-name="store.activeApp?.app_name"
			/>
		</template>

		<template #actions>
			<Button variant="solid" label="Update" @click="handleAppExport" class="w-full" />
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { Button } from "frappe-ui"
import { toast } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import { studioApps } from "@/data/studioApps"
import AppExportSettings from "@/components/AppExportSettings.vue"

const showDialog = defineModel("showDialog", { type: Boolean, required: true })

const store = useStudioStore()
const enableExport = ref(false)
const targetApp = ref("")

watch(
	() => [store.activeApp?.app_name, store.activeApp?.is_standard, store.activeApp?.frappe_app],
	() => {
		enableExport.value = Boolean(store.activeApp?.is_standard)
		targetApp.value = store.activeApp?.frappe_app || ""
	},
	{ immediate: true },
)

function handleAppExport() {
	enableExport.value ? exportApp() : disableAppExport()
}

function exportApp() {
	return studioApps.runDocMethod.submit(
		{
			name: store.activeApp?.app_name,
			method: "enable_app_export",
			target_app: targetApp.value,
		},
		{
			onSuccess: () => {
				store.setApp(store.activeApp!.name)
				toast.success("App exported successfully")
				showDialog.value = false
			},
			onError: (error: any) => {
				toast.error("Failed to export app", {
					description: error?.messages?.join(", "),
					duration: 500,
				})
			},
		},
	)
}

function disableAppExport() {
	return studioApps.runDocMethod.submit(
		{
			name: store.activeApp?.app_name,
			method: "disable_app_export",
		},
		{
			onSuccess: () => {
				store.setApp(store.activeApp!.name)
				toast.success("App export disabled")
				showDialog.value = false
			},
			onError: (error: any) => {
				toast.error("Failed to disable app export", {
					description: error?.messages?.join(", "),
					duration: 500,
				})
			},
		},
	)
}
</script>
