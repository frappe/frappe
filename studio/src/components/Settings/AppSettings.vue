<template>
	<SettingsHeader title="App" description="Settings for this app">
		<template #actions>
			<Button variant="solid" label="Save" :loading="saving" :disabled="!isDirty" @click="save" />
		</template>
	</SettingsHeader>
	<SettingsBody>
		<div class="flex flex-col gap-4 pt-6">
			<ErrorMessage :message="error" />
			<FormControl label="Title" type="text" variant="outline" v-model="app.app_title" :required="true" />
			<FormControl label="App Route" type="text" variant="outline" v-model="app.route" />
			<FormControl label="App Name" type="text" variant="outline" :model-value="appName" :disabled="true" />

			<hr class="border-outline-gray-2" />

			<div class="flex flex-col gap-3">
				<span class="text-base font-medium text-ink-gray-8">Favicon</span>
				<div class="flex items-center gap-5">
					<div
						class="flex items-center justify-center rounded border border-outline-gray-1 bg-surface-gray-2 px-12 py-5"
					>
						<img :src="app.favicon || DEFAULT_FAVICON" alt="App Favicon" class="size-6 rounded-sm" />
					</div>
					<div class="flex flex-col gap-2">
						<FileUploader
							file-types="image/*"
							:private="false"
							doctype="Studio App"
							:docname="appName"
							@success="(file: FileDoc) => (app.favicon = file.file_url)"
						>
							<template #default="{ uploading, progress, openFileSelector }">
								<div class="flex gap-2">
									<Button @click="openFileSelector">
										{{ uploading ? `Uploading ${progress}%` : app.favicon ? "Change" : "Upload" }}
									</Button>
									<Button v-if="app.favicon" @click="app.favicon = ''">Remove</Button>
								</div>
							</template>
						</FileUploader>
						<span class="text-p-sm text-ink-gray-6">
							Appears next to the title in the browser tab. Recommended size is 32x32 px in PNG or ICO.
						</span>
					</div>
				</div>
			</div>
		</div>
	</SettingsBody>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, ErrorMessage, FileUploader, FormControl, SettingsBody, SettingsHeader, toast } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import { studioApps } from "@/data/studioApps"

type FileDoc = { file_url: string }

const DEFAULT_FAVICON = "/assets/studio/frontend/favicon.png"

const store = useStudioStore()
const appName = store.activeApp!.name

const savedApp = computed(() => ({
	app_title: store.activeApp?.app_title || "",
	route: store.activeApp?.route || "",
	favicon: store.activeApp?.favicon || "",
}))
const app = ref({ ...savedApp.value })
const isDirty = computed(() => JSON.stringify(app.value) !== JSON.stringify(savedApp.value))

const error = ref("")
const saving = ref(false)

function save() {
	if (!app.value.app_title) {
		error.value = "Title is required"
		return
	}
	saving.value = true
	error.value = ""
	studioApps.setValue
		.submit({ name: appName, ...app.value })
		.then(async () => {
			await store.setApp(appName)
			toast.success("App settings saved")
		})
		.catch((e: any) => {
			error.value = e?.messages?.join(", ") || e?.message || "Failed to save app settings"
		})
		.finally(() => {
			saving.value = false
		})
}
</script>
