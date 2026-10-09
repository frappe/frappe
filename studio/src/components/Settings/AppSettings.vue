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
				label="Route"
				:description="appURL"
				:modelValue="app.route"
				:hideClearButton="true"
				@update:modelValue="(value: string) => update('route', value)"
			/>
		</div>
		<div class="flex gap-5">
			<Input
				type="select"
				label="App Home"
				:options="homeOptions"
				:modelValue="app.app_home"
				@update:modelValue="(value: string) => update('app_home', value)"
			/>
			<div class="w-full" />
		</div>
		<div class="flex flex-col gap-3 text-base">
			<div class="flex">
				<span class="w-24 text-ink-gray-6">App Name</span>
				<span class="font-medium text-ink-gray-8">{{ app.app_name || app.name }}</span>
			</div>
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
			<div class="flex flex-col gap-3">
				<span class="text-md-semibold text-ink-gray-9">Export</span>
				<AppExport />
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button, FileUploader, toast } from "frappe-ui"
import Input from "@/components/Input.vue"
import AppExport from "@/components/Settings/AppExport.vue"
import useStudioStore from "@/stores/studioStore"
import defaultFavicon from "/favicon.png"

type FileDoc = { file_url: string }

const store = useStudioStore()
const app = computed(() => store.activeApp)
const appURL = computed(() => `${window.location.origin}/${app.value?.route}`)
const homeOptions = computed(() =>
	Object.values(store.appPages).map((page) => ({ label: page.page_title, value: page.name })),
)
const isDeveloperMode = Boolean(window.is_developer_mode)

function update(field: "app_title" | "route" | "app_home" | "favicon", value: string) {
	store.updateActiveApp(field, value).catch((error: any) => {
		toast.error(error?.messages?.join(", ") || error?.message || "Failed to update the app")
	})
}
</script>
