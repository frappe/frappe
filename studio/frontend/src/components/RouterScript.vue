<template>
	<CodeEditorDock
		tab="Pages"
		:open="store.showRouterEditor"
		:modelValue="script"
		:completions="complete"
		@update:modelValue="onChange"
		@save="save"
	>
		<template #title>
			<span class="truncate text-sm text-ink-gray-8">{{ ROUTER_FILE }}</span>
			<Badge v-if="dirty" theme="amber" variant="subtle" label="Unsaved" />
		</template>
		<template #actions>
			<Popover side="bottom" align="end" :offset="6" bare>
				<template #trigger>
					<Button
						size="xs"
						variant="ghost"
						icon="lucide-circle-help"
						title="How to write the router script"
					/>
				</template>
				<div class="max-w-sm rounded-4 border border-outline-gray-2 bg-surface-base p-3 shadow-lg">
					<RouterScriptHelp />
				</div>
			</Popover>
			<Button
				v-if="savedScript"
				size="xs"
				variant="ghost"
				icon="lucide-trash-2"
				title="Delete router script"
				@click="remove"
			/>
			<Button size="xs" variant="solid" :loading="saving" :disabled="!dirty" @click="save">Save</Button>
			<Button size="xs" variant="ghost" icon="lucide-x" title="Close editor" @click="close" />
		</template>
		<template #banner>
			<ErrorMessage v-if="error" class="border-b border-outline-gray-2 px-3 py-2" :message="error" />
		</template>
	</CodeEditorDock>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue"
import type { CompletionContext } from "@codemirror/autocomplete"
import { toast, Badge, Button, Popover, ErrorMessage } from "frappe-ui"
import CodeEditorDock from "@/components/CodeEditorDock.vue"
import RouterScriptHelp from "@/components/RouterScriptHelp.vue"
import { deleteStudioFile, readStudioFileIfExists, writeStudioFile } from "@/data/studioFiles"
import { routerScriptCompletions } from "@/utils/completions/routerScriptCompletions"
import { confirm } from "@/utils/helpers"
import useStudioStore from "@/stores/studioStore"

const ROUTER_FILE = "router.ts"
const BOILERPLATE = `{
	setup(router) {
		// e.g. send users who have not finished onboarding to the Onboarding page
		// router.beforeEach((to) => {
		// 	if (boot.onboarding_complete === false && to.name !== "Onboarding") return { name: "Onboarding" }
		// })
	},
}`

const store = useStudioStore()

const script = ref("")
const savedScript = ref("")
const fileHash = ref<string | undefined>()
const saving = ref(false)
const error = ref<string | null>(null)
const dirty = computed(() => script.value !== savedScript.value)

const location = computed(() => ({
	frappe_app: store.activeApp?.frappe_app ?? "",
	studio_app: store.activeApp?.name ?? "",
}))

// Both app types use router.ts, stored in the repository or database file store.
async function load() {
	const file = await readStudioFileIfExists(location.value, ROUTER_FILE)
	setLoaded(file.content ?? "", file.hash ?? undefined)
	if (file.content === null) script.value = `export default ${BOILERPLATE}\n`
}

async function saveFile(source: string) {
	const result = await writeStudioFile(location.value, ROUTER_FILE, source, fileHash.value)
	fileHash.value = result.hash
	if (store.usesDbFiles) store.refreshAppFiles()
}

async function removeFile() {
	await deleteStudioFile(location.value, ROUTER_FILE)
	if (store.usesDbFiles) store.refreshAppFiles()
}

function complete(context: CompletionContext) {
	return routerScriptCompletions(context, Object.values(store.appPages))
}

watch(
	() => store.showRouterEditor && store.activeApp?.name,
	async (openForApp) => {
		if (!openForApp) return
		try {
			await load()
		} catch (loadError: any) {
			store.showRouterEditor = false
			toast.error("Failed to open the router script", { description: loadError?.messages?.join(", ") })
		}
	},
	{ immediate: true },
)

function setLoaded(content: string, hash?: string) {
	script.value = content
	savedScript.value = content
	fileHash.value = hash
	error.value = null
}

function onChange(value: string) {
	// the editor also emits on blur, so clicking Save must not wipe the error it is about to show
	if (value !== script.value) error.value = null
	script.value = value
}

async function save() {
	if (!dirty.value) return
	saving.value = true
	try {
		await saveFile(script.value)
		savedScript.value = script.value
		toast.success("Saved the router script")
	} catch (saveError: any) {
		error.value = saveError?.messages?.join(", ") || saveError?.message || "Failed to save the router script"
	} finally {
		saving.value = false
	}
}

async function remove() {
	if (!(await confirm("The app goes back to Studio's default routing.", "Delete router script?"))) return
	try {
		await removeFile()
		store.showRouterEditor = false
		toast.success("Deleted the router script")
	} catch (removeError: any) {
		toast.error("Failed to delete the router script", { description: removeError?.messages?.join(", ") })
	}
}

async function close() {
	if (dirty.value && !(await confirm("Discard unsaved changes?"))) return
	store.showRouterEditor = false
}
</script>
