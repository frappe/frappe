<template>
	<div v-if="app" class="flex flex-col gap-6 px-[2px]">
		<div class="flex gap-5">
			<Input
				label="Title"
				:modelValue="app.app_title"
				:hideClearButton="true"
				@update:modelValue="(value: string) => update('app_title', value)"
			/>
			<Input
				type="select"
				label="App Home"
				:options="homeOptions"
				:modelValue="app.app_home"
				@update:modelValue="(value: string) => update('app_home', value)"
			/>
		</div>
		<div class="flex items-start gap-5">
			<Input
				label="Route"
				:description="appURL"
				:modelValue="app.route"
				:hideClearButton="true"
				@update:modelValue="(value: string) => update('route', value)"
			/>
			<AppRenameDialog />
		</div>

		<hr class="w-full border-outline-gray-2" />

		<div class="flex flex-col gap-5">
			<span class="text-md-semibold text-ink-gray-9">Favicon</span>
			<div class="flex flex-1 gap-5">
				<div
					class="flex items-center justify-center rounded-4 border border-outline-gray-1 bg-surface-gray-2 px-20 py-5"
				>
					<img :src="app.favicon || defaultFavicon" alt="App Favicon" class="size-6 rounded-4" />
				</div>
				<div class="flex flex-1 flex-col gap-2">
					<FileUploader
						file-types="image/*"
						:private="false"
						doctype="Studio App"
						:docname="app.name"
						class="text-base"
						@success="(file: FileDoc) => update('favicon', file.file_url)"
					>
						<template #default="{ uploading, progress, openFileSelector }">
							<div class="flex items-end gap-2">
								<Button @click="openFileSelector">
									{{ uploading ? `Uploading ${progress}%` : app.favicon ? "Change" : "Upload" }}
								</Button>
								<Button v-if="app.favicon" @click="update('favicon', '')">Remove</Button>
							</div>
						</template>
					</FileUploader>
					<span class="text-p-sm text-ink-gray-6">
						Appears next to the title in the browser tab. Recommended size is 32x32 px in PNG or ICO
					</span>
				</div>
			</div>
		</div>

		<template v-if="isDeveloperMode">
			<hr class="w-full border-outline-gray-2" />
			<div class="flex items-center justify-between gap-5">
				<div class="flex flex-col gap-1.5">
					<span class="text-md-semibold text-ink-gray-9">Export</span>
					<span v-if="app.is_standard && app.frappe_app" class="text-p-sm text-ink-gray-6">
						Exported to
						<code class="rounded-1 bg-surface-gray-2 px-1 py-0.5 font-mono text-ink-gray-8">{{ exportFolder }}</code>
					</span>
					<span v-else class="text-p-sm text-ink-gray-6">Not exported to any Frappe App</span>
				</div>
				<Button label="Edit" @click="showExportDialog = true" />
			</div>
			<ExportAppDialog v-model:showDialog="showExportDialog" />
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, FileUploader, toast } from "frappe-ui"
import Input from "@/components/Input.vue"
import AppRenameDialog from "@/components/Settings/AppRenameDialog.vue"
import ExportAppDialog from "@/components/ExportAppDialog.vue"
import useStudioStore from "@/stores/studioStore"
import { scrub } from "@/utils/helpers"
import defaultFavicon from "/favicon.png"

type FileDoc = { file_url: string }

const store = useStudioStore()
const app = computed(() => store.activeApp)
const appURL = computed(() => `${window.location.origin}/${app.value?.route}`)
const homeOptions = computed(() =>
	Object.values(store.appPages).map((page) => ({ label: page.page_title, value: page.name })),
)
const isDeveloperMode = Boolean(window.is_developer_mode)
const showExportDialog = ref(false)
const exportFolder = computed(() => `${app.value?.frappe_app}/studio/${scrub(app.value?.app_name || "")}`)

const FIELD_LABELS = { app_title: "Title", route: "Route", app_home: "App Home", favicon: "Favicon" }

function update(field: keyof typeof FIELD_LABELS, value: string) {
	const label = FIELD_LABELS[field]
	store
		.updateActiveApp(field, value)
		.then(() => toast.success(`${label} saved`))
		.catch((error: any) => {
			toast.error(`Could not save ${label}`, { description: error?.messages?.join(", ") || error?.message })
		})
}
</script>
