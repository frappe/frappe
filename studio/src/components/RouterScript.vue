<template>
	<CodeEditorDock
		tab="Pages"
		:open="store.showRouterEditor"
		:modelValue="script"
		@update:modelValue="onChange"
		@save="save"
	>
		<template #title>
			<span class="truncate text-sm text-ink-gray-8">{{ source.title }}</span>
			<span v-if="dirty" class="text-ink-amber-5">•</span>
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
				v-if="store.hasRouterScript"
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
import { toast, Button, Popover, ErrorMessage } from "frappe-ui"
import CodeEditorDock from "@/components/CodeEditorDock.vue"
import RouterScriptHelp from "@/components/RouterScriptHelp.vue"
import { createStudioFile, deleteStudioFile, readStudioFile, writeStudioFile } from "@/data/studioFiles"
import { getScriptError } from "@/utils/parseCode"
import { confirm } from "@/utils/helpers"
import useStudioStore from "@/stores/studioStore"

const ROUTER_FILE = "router.ts"
const BOILERPLATE = `{
	// runs once before the first navigation
	setup(router) {
		router.beforeEach((to, from) => {
			// return false to cancel, or a location to redirect
		})

		router.afterEach((to, from) => {
			// e.g. track page views
		})
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

// standard apps keep the router config in studio/<app>/router.ts, custom apps in the app doc
const fileSource = {
	title: ROUTER_FILE,
	async load() {
		if (!store.hasRouterFile) return createFile()
		const file = await readStudioFile(location.value, ROUTER_FILE)
		setLoaded(file.content, file.hash)
	},
	async save(source: string) {
		const result = await writeStudioFile(location.value, ROUTER_FILE, source, fileHash.value)
		fileHash.value = result.hash
	},
	async remove() {
		await deleteStudioFile(location.value, ROUTER_FILE)
		store.hasRouterFile = false
	},
}

const fieldSource = {
	title: "Router Script",
	async load() {
		const saved = store.activeApp?.router_script || ""
		setLoaded(saved)
		if (!saved) script.value = BOILERPLATE
	},
	async save(source: string) {
		// an object literal only parses as an expression
		const syntaxError = source.trim() ? getScriptError(`(${source})`) : null
		if (syntaxError) throw new Error(syntaxError.message)
		await store.updateActiveApp("router_script", source)
	},
	remove: () => store.updateActiveApp("router_script", ""),
}

const source = computed(() => (store.activeApp?.is_standard ? fileSource : fieldSource))

watch(
	() => store.showRouterEditor && store.activeApp?.name,
	async (openForApp) => {
		if (!openForApp) return
		try {
			await source.value.load()
		} catch (loadError: any) {
			store.showRouterEditor = false
			toast.error("Failed to open the router script", { description: loadError?.messages?.join(", ") })
		}
	},
	{ immediate: true },
)

async function createFile() {
	const starter = `export default ${BOILERPLATE}\n`
	const created = await createStudioFile(location.value, ROUTER_FILE)
	const written = await writeStudioFile(location.value, ROUTER_FILE, starter, created.hash)
	store.hasRouterFile = true
	setLoaded(starter, written.hash)
}

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
		await source.value.save(script.value)
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
		await source.value.remove()
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
