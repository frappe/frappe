<template>
	<Dialog
		v-model="showDialog"
		:options="{
			title: `Export ${props.appTitle} App`,
			dialog: 'sm',
		}"
		@after-leave="
			() => {
				targetApp = ''
			}
		"
	>
		<template #body-content>
			<div class="flex flex-col space-y-4">
				<FormControl
					label="Frappe App"
					:required="true"
					type="autocomplete"
					placeholder="Select the target Frappe App"
					:modelValue="targetApp"
					@update:modelValue="(v: SelectOption) => (targetApp = v.value || '')"
					:options="targetAppOptions"
				/>
			</div>
		</template>

		<template #actions>
			<Button variant="solid" label="Export" @click="() => exportApp()" class="w-full" />
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { FormControl, Button, call } from "frappe-ui"
import type { SelectOption } from "@/types"
import { studioApps } from "@/data/studioApps"
import { toast } from "vue-sonner"

const props = defineProps<{
	appName: string
	appTitle: string
}>()
const showDialog = defineModel("showDialog", { type: Boolean, required: true })

const targetApp = ref("")
let targetAppOptions: string[] = []

call("frappe.core.doctype.module_def.module_def.get_installed_apps").then((data: string[]) => {
	if (typeof data === "string") {
		data = JSON.parse(data)
	}
	targetAppOptions = data || []
})

function exportApp() {
	return studioApps.runDocMethod.submit(
		{
			name: props.appName,
			method: "export_app",
			target_app: targetApp.value,
		},
		{
			onSuccess() {
				toast.success("App exported successfully")
			},
			onError(error: any) {
				toast.error("Failed to export app", {
					description: error?.messages?.join(", "),
					duration: Infinity,
				})
			},
		},
	)
}
</script>
