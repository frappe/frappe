<template>
	<Dialog
		v-model="showDialog"
		:options="{
			title: 'Export Settings',
			size: 'xl',
		}"
	>
		<template #body-content>
			<div class="flex flex-col space-y-4">
				<Switch
					size="sm"
					label="Enable App Export"
					description="Exports app changes to an existing Frappe App"
					v-model="enableExport"
				/>
				<div v-if="enableExport" class="flex flex-col space-y-1.5">
					<span class="text-base font-medium leading-normal text-ink-gray-8">Frappe App</span>
					<FormControl
						:required="true"
						type="autocomplete"
						placeholder="Select the target Frappe App"
						:description="`App will be exported to ${targetApp || 'frappe_app_name'}/studio/${scrub(store.activeApp?.app_name)}`"
						:modelValue="targetApp"
						@update:modelValue="(v: SelectOption) => (targetApp = v.value || '')"
						:options="targetAppOptions"
					/>
				</div>
			</div>
		</template>

		<template #actions>
			<Button variant="solid" label="Update" @click="handleAppExport" class="w-full" />
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { FormControl, Button, call, Switch } from "frappe-ui"
import type { SelectOption } from "@/types"
import { toast } from "vue-sonner"
import useStudioStore from "@/stores/studioStore"
import { studioApps } from "@/data/studioApps"
import { scrub } from "@/utils/helpers"

const showDialog = defineModel("showDialog", { type: Boolean, required: true })

const store = useStudioStore()
const enableExport = ref(store.activeApp?.is_standard || false)
const targetApp = ref(store.activeApp?.frappe_app)
let targetAppOptions: string[] = []

call("frappe.core.doctype.module_def.module_def.get_installed_apps").then((data: string[]) => {
	if (typeof data === "string") {
		data = JSON.parse(data)
	}
	targetAppOptions = data || []
})

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
				toast.success("App exported successfully")
				showDialog.value = false
			},
			onError: (error: any) => {
				toast.error("Failed to export app", {
					description: error?.messages?.join(", "),
					duration: Infinity,
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
				toast.success("App export disabled")
				showDialog.value = false
			},
			onError: (error: any) => {
				toast.error("Failed to disable app export", {
					description: error?.messages?.join(", "),
					duration: Infinity,
				})
			},
		},
	)
}
</script>
