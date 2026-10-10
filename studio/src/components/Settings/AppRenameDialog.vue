<template>
	<div class="flex w-full items-end gap-2">
		<FormControl label="App Name" type="text" class="w-full" :modelValue="appName" :disabled="true" />
		<Tooltip :text="renameBlockedReason" :disabled="!renameBlockedReason">
			<span>
				<Button label="Rename" :disabled="Boolean(renameBlockedReason)" @click="openDialog" />
			</span>
		</Tooltip>

		<Dialog v-model:open="showDialog" title="Rename App" size="md">
			<template #default>
				<div class="flex flex-col gap-3">
					<FormControl
						label="App Name"
						type="text"
						variant="outline"
						v-model="newName"
						description="Lowercase letters, numbers, hyphens and underscores"
					/>
					<p class="text-p-sm text-ink-gray-6">
						The editor's URL changes to the new name. The app's route stays the same. If the app is
						published, publish it again to rebuild it under the new name.
						<template v-if="store.activeApp?.is_standard">
							Its export folder moves to {{ store.activeApp.frappe_app }}/studio/{{ scrub(newName) || "…" }}.
						</template>
					</p>
				</div>
			</template>
			<template #actions>
				<div class="flex flex-col gap-2">
					<ErrorMessage :message="error" />
					<Button
						variant="solid"
						label="Rename"
						class="w-full"
						:loading="renaming"
						:disabled="!newName || newName === appName"
						@click="rename"
					/>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Button, Dialog, ErrorMessage, FormControl, Tooltip, call, toast } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import { studioApps } from "@/data/studioApps"
import { scrub } from "@/utils/helpers"

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
const showDialog = ref(false)
const newName = ref("")
const error = ref("")
const renaming = ref(false)

function openDialog() {
	newName.value = appName.value
	error.value = ""
	showDialog.value = true
}

async function rename() {
	renaming.value = true
	error.value = ""
	try {
		const name = (await call("frappe.client.rename_doc", {
			doctype: "Studio App",
			old_name: appName.value,
			new_name: newName.value.trim(),
		})) as string
		await openRenamedApp(name)
		showDialog.value = false
		toast.success("App renamed")
	} catch (renameError: any) {
		error.value = renameError?.messages?.join(", ") || renameError?.message || "Failed to rename the app"
	} finally {
		renaming.value = false
	}
}

async function openRenamedApp(name: string) {
	await router.replace({ name: route.name!, params: { ...route.params, appID: name } })
	await store.setApp(name)
	studioApps.reload()
}
</script>
