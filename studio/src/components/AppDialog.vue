<template>
	<Dialog
		v-model="showDialog"
		:title="isEditing ? 'Edit App' : 'New App'"
		width="md"
		@after-leave="
			() => {
				activeApp = { ...emptyAppState }
				error = ''
			}
		"
	>
		<template #default>
			<div class="flex flex-col gap-3">
				<FormControl
					label="Title"
					type="text"
					variant="outline"
					v-model="activeApp.app_title"
					@input="setAppFields"
					:required="true"
				/>
				<FormControl label="App Route" type="text" variant="outline" v-model="activeApp.route" />
				<FormControl
					label="App Name"
					type="text"
					variant="outline"
					v-model="activeApp.app_name"
					:placeholder="activeApp.app_name_placeholder"
					:disabled="isEditing"
				/>

				<AppExportSettings
					v-if="!isEditing && isDeveloperMode"
					v-model:enableExport="enableExport"
					v-model:targetApp="targetApp"
					:app-name="activeApp.app_name || activeApp.app_name_placeholder"
				/>
			</div>
		</template>

		<template #actions>
			<div class="space-y-2">
				<ErrorMessage :message="error" />
				<Button
					variant="solid"
					:label="isEditing ? 'Update' : 'Create'"
					@click="() => handleSave()"
					class="w-full"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script lang="ts" setup>
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { studioApps } from "@/data/studioApps"
import { Dialog, FormControl, ErrorMessage, Button } from "frappe-ui"
import type { StudioApp } from "@/types/Studio/StudioApp"
import { toast } from "frappe-ui"
import AppExportSettings from "@/components/AppExportSettings.vue"

const props = defineProps<{ app?: StudioApp | null }>()
const showDialog = defineModel("showDialog", { type: Boolean, required: true })

const emptyAppState = {
	app_title: "",
	route: "",
	app_name: "",
	app_name_placeholder: "",
	name: "",
}
const activeApp = ref({ ...emptyAppState })

const enableExport = ref(false)
const targetApp = ref("")
const isDeveloperMode = Boolean(window.is_developer_mode)

watch(
	() => showDialog.value,
	() => {
		enableExport.value = false
		targetApp.value = ""
		if (props.app?.name) {
			activeApp.value = {
				app_title: props.app.app_title,
				route: props.app.route,
				app_name: props.app.app_name,
				app_name_placeholder: props.app.name,
				name: props.app.name,
			}
		} else {
			activeApp.value = { ...emptyAppState }
		}
	},
	{ immediate: true },
)

const error = ref("")
const router = useRouter()

const isEditing = computed(() => !!props.app?.name)

function handleSave() {
	if (isEditing.value) {
		updateStudioApp()
	} else {
		createStudioApp()
	}
}

const createStudioApp = () => {
	const { app_title, route, app_name } = activeApp.value
	if (enableExport.value && !targetApp.value) {
		error.value = "Select a Frappe App to export to, or disable app export."
		return
	}
	studioApps.insert.submit(
		{
			app_title: app_title,
			route: route,
			app_name: app_name,
			is_standard: enableExport.value ? 1 : 0,
			frappe_app: enableExport.value ? targetApp.value : null,
		},
		{
			onSuccess(res: StudioApp) {
				showDialog.value = false
				error.value = ""
				router.push({ name: "StudioApp", params: { appID: res.name } })
			},
			onError(reqError: any) {
				error.value = reqError.messages.join(", ")
			},
		},
	)
}

const emit = defineEmits(["update"])
const updateStudioApp = () => {
	studioApps.setValue.submit(
		{
			name: activeApp.value.name,
			app_title: activeApp.value.app_title,
			route: activeApp.value.route,
			app_name: activeApp.value.app_name,
		},
		{
			onSuccess(data: StudioApp) {
				showDialog.value = false
				error.value = ""
				toast.success(`App ${activeApp.value.app_title} updated`)
				emit("update", data)
			},
			onError(error: any) {
				error.value = error.messages.join(", ")
			},
		},
	)
}

function setAppFields(e: Event) {
	if (isEditing.value) return
	const kebabCasedTitle = (e.target as HTMLInputElement).value.toLowerCase().replace(/\s+/g, "-")
	activeApp.value.route = activeApp.value.app_name_placeholder = kebabCasedTitle
}
</script>
