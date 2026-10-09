<template>
	<div class="flex flex-col gap-3">
		<AppExportSettings
			v-model:enableExport="enableExport"
			v-model:targetApp="targetApp"
			:app-name="store.activeApp?.app_name"
		/>
		<div v-if="hasChanges" class="flex justify-end">
			<Button
				variant="solid"
				label="Update"
				:loading="updating"
				:disabled="enableExport && !targetApp"
				@click="updateExport"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, toast } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import { studioApps } from "@/data/studioApps"
import AppExportSettings from "@/components/AppExportSettings.vue"

const emit = defineEmits<{ updated: [] }>()

const store = useStudioStore()
const enableExport = ref(false)
const targetApp = ref("")
const updating = ref(false)

watch(
	() => [store.activeApp?.app_name, store.activeApp?.is_standard, store.activeApp?.frappe_app],
	() => {
		enableExport.value = Boolean(store.activeApp?.is_standard)
		targetApp.value = store.activeApp?.frappe_app || ""
	},
	{ immediate: true },
)

const hasChanges = computed(
	() =>
		enableExport.value !== Boolean(store.activeApp?.is_standard) ||
		(enableExport.value && targetApp.value !== (store.activeApp?.frappe_app || "")),
)

async function updateExport() {
	updating.value = true
	try {
		await (enableExport.value ? exportApp() : disableAppExport())
		await store.setApp(store.activeApp!.name)
		emit("updated")
	} catch (error: any) {
		const action = enableExport.value ? "export app" : "disable app export"
		toast.error(`Failed to ${action}`, { description: error?.messages?.join(", ") })
	} finally {
		updating.value = false
	}
}

async function exportApp() {
	await studioApps.runDocMethod.submit({
		name: store.activeApp?.app_name,
		method: "enable_app_export",
		target_app: targetApp.value,
	})
	toast.success("App exported")
}

async function disableAppExport() {
	const data = await studioApps.runDocMethod.submit({
		name: store.activeApp?.app_name,
		method: "disable_app_export",
	})
	if (data?.message) toast.warning("App export disabled", { description: data.message, duration: Infinity })
	else toast.success("App export disabled")
}
</script>
