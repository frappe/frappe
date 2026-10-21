<template>
	<Dialog v-model:open="showDialog" title="Export Settings" size="xl">
		<template #default>
			<AppExportSettings
				v-model:enableExport="enableExport"
				v-model:targetApp="targetApp"
				:app-name="store.activeApp?.app_name"
			/>
		</template>
		<template #actions>
			<div class="flex justify-end">
				<Button variant="solid" label="Update" :loading="updating" :disabled="!canUpdate" @click="update" />
			</div>
		</template>
	</Dialog>
	<Dialog :open="Boolean(prompt)" :title="prompt?.title" size="md" @update:open="(open: boolean) => !open && answer(false)">
		<template #default>
			<p class="text-p-base text-ink-gray-7">
				<template v-for="(segment, index) in prompt?.segments" :key="index">
					<code
						v-if="typeof segment !== 'string'"
						class="rounded-1 bg-surface-gray-2 px-1 py-0.5 font-mono text-p-sm text-ink-gray-8"
						>{{ segment.path }}</code
					>
					<template v-else>{{ segment }}</template>
				</template>
			</p>
		</template>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="answer(false)" />
				<Button variant="solid" label="Confirm" @click="answer(true)" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Dialog, toast } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import { studioApps } from "@/data/studioApps"
import { scrub } from "@/utils/helpers"
import AppExportSettings from "@/components/AppExportSettings.vue"

type Prompt = { title: string; segments: (string | { path: string })[]; resolve: (confirmed: boolean) => void }

const showDialog = defineModel("showDialog", { type: Boolean, required: true })

const store = useStudioStore()
const enableExport = ref(false)
const targetApp = ref("")
const updating = ref(false)
const prompt = ref<Prompt | null>(null)

watch(
	() => [showDialog.value, store.activeApp?.app_name, store.activeApp?.is_standard, store.activeApp?.frappe_app],
	() => {
		enableExport.value = Boolean(store.activeApp?.is_standard)
		targetApp.value = store.activeApp?.frappe_app || ""
	},
	{ immediate: true },
)

const exportedTo = computed(() => (store.activeApp?.is_standard ? store.activeApp?.frappe_app || "" : ""))
const hasChanges = computed(
	() => enableExport.value !== Boolean(exportedTo.value) || (enableExport.value && targetApp.value !== exportedTo.value),
)
const canUpdate = computed(() => hasChanges.value && !(enableExport.value && !targetApp.value))

async function update() {
	if (!(await confirmChange())) return
	updating.value = true
	try {
		await (enableExport.value ? exportApp() : disableAppExport())
		await store.setApp(store.activeApp!.name)
		showDialog.value = false
	} catch (error: any) {
		const action = enableExport.value ? "export app" : "disable app export"
		toast.error(`Failed to ${action}`, { description: error?.messages?.join(", ") })
	} finally {
		updating.value = false
	}
}

function confirmChange() {
	if (!exportedTo.value) return Promise.resolve(true)
	if (!enableExport.value) {
		return ask("Disable App Export", [
			"This copies the page and router scripts back into the app and deletes its export folder ",
			{ path: exportFolder(exportedTo.value) },
			".",
		])
	}
	return ask("Change Frappe App", [
		"The export folder moves from ",
		{ path: exportFolder(exportedTo.value) },
		" to ",
		{ path: exportFolder(targetApp.value) },
		`, with all its files. If the app is published, publish it again to rebuild it in ${targetApp.value}.`,
	])
}

function exportFolder(frappeApp: string) {
	return `${frappeApp}/studio/${scrub(store.activeApp?.app_name || "")}`
}

function ask(title: string, segments: Prompt["segments"]) {
	return new Promise<boolean>((resolve) => (prompt.value = { title, segments, resolve }))
}

function answer(confirmed: boolean) {
	prompt.value?.resolve(confirmed)
	prompt.value = null
}

async function exportApp() {
	await studioApps.runDocMethod.submit({
		name: store.activeApp?.app_name,
		method: "enable_app_export",
		target_app: targetApp.value,
	})
	toast.success("App exported")
}

async function disableAppExport() {
	const data = await studioApps.runDocMethod.submit({
		name: store.activeApp?.app_name,
		method: "disable_app_export",
	})
	if (data?.message) toast.warning("App export disabled", { description: data.message, duration: Infinity })
	else toast.success("App export disabled")
}
</script>
