<template>
	<div class="flex w-full items-end gap-2">
		<FormControl label="App Name" type="text" class="w-full" :modelValue="appName" :disabled="true" />
		<Button label="Rename" @click="openDialog" />

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
						The editor's URL changes to the new name. The app's route stays the same.
						<template v-if="store.activeApp?.is_standard">
							Its export folder moves to {{ store.activeApp.frappe_app }}/studio/{{ newName || "…" }}.
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
import { Button, Dialog, ErrorMessage, FormControl, toast } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import { studioApps } from "@/data/studioApps"

const store = useStudioStore()
const route = useRoute()
const router = useRouter()

const appName = computed(() => store.activeApp?.name || "")
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
		const response = await studioApps.runDocMethod.submit({
			name: appName.value,
			method: "rename_app",
			new_name: newName.value.trim(),
		})
		const { name, stale_build } = response.message
		await openRenamedApp(name)
		showDialog.value = false
		notifyRenamed(stale_build)
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

function notifyRenamed(staleBuild: boolean) {
	if (!staleBuild) {
		toast.success("App renamed")
		return
	}
	toast.warning("App renamed. Publish it again to rebuild it", {
		description:
			"The app's build still uses the old name, so the published app runs on the default renderer until it is rebuilt.",
		duration: Infinity,
	})
}
</script>
