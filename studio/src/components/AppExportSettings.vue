<template>
	<div class="flex flex-col gap-3">
		<SettingItem label="Enable App Export" description="Export app changes to an existing Frappe App">
			<Switch size="sm" v-model="enableExport" />
		</SettingItem>
		<SettingItem
			v-if="enableExport"
			label="Frappe App"
			:description="`Exported to ${targetApp || 'frappe_app'}/studio/${scrub(appName)}`"
		>
			<FormControl type="combobox" placeholder="Select App" v-model="targetApp" :options="targetAppOptions" />
		</SettingItem>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { FormControl, Switch, call } from "frappe-ui"
import { scrub } from "@/utils/helpers"
import SettingItem from "@/components/SettingItem.vue"

defineProps<{ appName?: string | null }>()
const enableExport = defineModel<boolean>("enableExport", { required: true })
const targetApp = defineModel<string>("targetApp", { required: true })

const targetAppOptions = ref<string[]>([])
call("frappe.core.doctype.module_def.module_def.get_installed_apps").then((data: string[] | string) => {
	const apps = typeof data === "string" ? JSON.parse(data) : data
	targetAppOptions.value = apps || []
})
</script>
