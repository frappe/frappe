<template>
	<Dialog
		v-model="showDialog"
		:options="{
			title: `Export ${props.appTitle} App`,
			dialog: 'sm',
		}"
		@after-leave="
			() => {
				exportConfig.targetApp = ''
				exportConfig.targetModule = ''
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
					:modelValue="exportConfig.targetApp"
					@update:modelValue="(v: SelectOption) => (exportConfig.targetApp = v.value || '')"
					:options="targetAppOptions"
				/>
				<Link
					label="Module"
					:required="true"
					doctype="Module Def"
					:filters="targetModuleFilters"
					v-model="exportConfig.targetModule"
				/>
			</div>
		</template>

		<template #actions>
			<Button variant="solid" label="Export" @click="() => exportApp()" class="w-full" />
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { FormControl, Button, call } from "frappe-ui"
import Link from "@/components/Link.vue"
import type { SelectOption } from "@/types"
import { studioApps } from "@/data/studioApps"
import { toast } from "vue-sonner"

const props = defineProps<{
	appName: string
	appTitle: string
}>()
const showDialog = defineModel("showDialog", { type: Boolean, required: true })

const exportConfig = ref({
	targetApp: "",
	targetModule: "",
})
let targetAppOptions: string[] = []
let targetModuleFilters = ref({})

call("frappe.core.doctype.module_def.module_def.get_installed_apps").then((data: string[]) => {
	if (typeof data === "string") {
		data = JSON.parse(data)
	}
	targetAppOptions = data || []
})

watch(
	() => exportConfig.value.targetApp,
	(targetApp) => {
		if (targetApp) {
			targetModuleFilters.value = { app_name: targetApp }
		} else {
			targetModuleFilters.value = {}
		}
	},
)

function exportApp() {
	return studioApps.runDocMethod.submit(
		{
			name: props.appName,
			method: "export_app",
			target_module: exportConfig.value.targetModule,
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
