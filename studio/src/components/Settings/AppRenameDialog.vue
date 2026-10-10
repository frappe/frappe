<template>
	<div class="flex w-full items-end gap-2">
		<FormControl label="App Name" type="text" class="w-full" :modelValue="appName" :disabled="true" />
		<Tooltip :text="renameBlockedReason" :disabled="!renameBlockedReason">
			<span>
				<Button label="Rename" :disabled="Boolean(renameBlockedReason)" @click="openDialog" />
			</span>
		</Tooltip>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Button, FormControl, Tooltip, call, dialog, toast } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import { studioApps } from "@/data/studioApps"

const store = useStudioStore()
const route = useRoute()
const router = useRouter()

const appName = computed(() => store.activeApp?.name || "")
// the export folder is named after the app and only moves with it in developer mode
const renameBlockedReason = computed(() =>
	store.activeApp?.is_standard && !window.is_developer_mode
		? "Exported apps can only be renamed in developer mode"
		: "",
)

function openDialog() {
	dialog.prompt({
		title: "Rename App",
		message: renameNote(),
		fields: [
			{
				name: "app_name",
				label: "App Name",
				defaultValue: appName.value,
				required: true,
				description: "Lowercase, with hyphens instead of spaces",
				validate: (value: string) => (value.trim() === appName.value ? "Enter a new name" : null),
			},
		],
		confirmLabel: "Rename",
		onConfirm: ({ values }: { values: Record<string, string> }) => rename(values.app_name.trim()),
	})
}

function renameNote() {
	const note =
		"The editor's URL changes to the new name. The app's route stays the same. If the app is published, publish it again to rebuild it under the new name."
	return store.activeApp?.is_standard ? `${note} Its export folder moves with it.` : note
}

async function rename(newName: string) {
	const name = (await call("frappe.client.rename_doc", {
		doctype: "Studio App",
		old_name: appName.value,
		new_name: newName,
	})) as string
	await router.replace({ name: route.name!, params: { ...route.params, appID: name } })
	await store.setApp(name)
	studioApps.reload()
	toast.success("App renamed")
}
</script>
