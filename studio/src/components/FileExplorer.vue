<template>
	<div class="flex flex-col gap-2">
		<!-- File tree -->
		<div class="flex items-center justify-between">
			<div class="flex flex-col gap-2">
				<span class="text-sm font-medium text-ink-gray-7">{{ app.app_name }}/studio</span>
			</div>
			<div class="flex items-center gap-1">
				<Button variant="ghost" icon="lucide-plus" @click="openNewFileDialog" title="New file" />
				<Button
					variant="ghost"
					icon="lucide-refresh-cw"
					:loading="loading"
					@click="loadTree"
					title="Refresh"
				/>
			</div>
		</div>

		<button
			v-if="activePage"
			class="flex w-full items-center gap-2 rounded border border-outline-gray-2 px-2 py-1.5 text-left hover:bg-surface-gray-2"
			:title="
				activePageHasScript
					? `Open ${activePage.page_title}'s script`
					: `Add a script for ${activePage.page_title}`
			"
			@click="openActivePageScript"
		>
			<span class="lucide-file size-3.5 shrink-0 text-ink-gray-5" />
			<span class="flex min-w-0 flex-1 flex-row">
				<span class="block text-sm text-ink-gray-5">Editing&nbsp;</span>
				<span class="block truncate text-sm text-ink-gray-8">{{ activePage.page_title }}</span>
			</span>
			<span class="shrink-0 text-xs text-ink-gray-5">
				{{ activePageHasScript ? "Open script" : "Add script" }}
			</span>
		</button>

		<div class="overflow-auto rounded">
			<EmptyState v-if="!loading && !tree.length" message="No code files yet" />
			<Tree v-for="node in tree" :key="node.path" :node="node" nodeKey="path" :options="treeOptions">
				<template #node="{ node, isCollapsed, toggleCollapsed }">
					<div
						class="flex h-7 cursor-pointer select-none items-center gap-1 rounded px-1"
						:class="
							selectedNode?.path === node.path
								? 'bg-surface-gray-3 text-ink-gray-9'
								: 'text-ink-gray-7 hover:bg-surface-gray-2'
						"
						@click="onNodeClick(node, toggleCollapsed, $event)"
					>
						<div class="mt-[1.25px] flex w-5 shrink-0 flex-col items-center justify-center">
							<span
								v-if="node.is_folder"
								class="size-3.5 items-center text-ink-gray-5"
								:class="isCollapsed ? 'lucide-chevron-right' : 'lucide-chevron-down'"
							/>
							<span
								v-else
								class="font-mono text-[10px] font-bold leading-5"
								:class="getFileBadge(node.path).colorClass"
							>
								{{ getFileBadge(node.path).label }}
							</span>
						</div>
						<div
							class="min-w-0 flex-1 truncate text-sm"
							:class="node.path === activePagePaths?.folder ? 'font-medium text-ink-gray-9' : ''"
						>
							{{ node.label }}
						</div>
						<Tooltip
							v-if="node.path === activePagePaths?.folder"
							text="Currently editing this page"
							placement="right"
						>
							<span class="ml-1 mt-0.5 shrink-0 text-[8px] text-ink-blue-3">●</span>
						</Tooltip>
					</div>
				</template>
			</Tree>
		</div>
	</div>

	<Dialog v-model="showNewFileDialog" title="New File" width="md">
		<template #default>
			<FormControl
				ref="pathInput"
				type="text"
				variant="outline"
				label="File path"
				:description="`Relative to studio/${app.app_name}. Allowed: .ts, .js, .vue, .json, .css`"
				placeholder="composables/useThing.ts"
				v-model="newFilePath"
				@keyup.enter="createFile"
			/>
		</template>
		<template #actions>
			<Button variant="solid" label="Create" class="w-full" @click="createFile" />
		</template>
	</Dialog>

	<!-- Editor docks beside the left panel at full height -->
	<Teleport to="#studio-code-editor-outlet">
		<div
			v-if="showEditor"
			class="absolute bottom-0 top-[var(--toolbar-height)] z-20 flex flex-col bg-white shadow-lg"
			:style="{ left: `${panelLeft}px`, width: `${editorWidth}px` }"
		>
			<PanelResizer
				side="right"
				:dimension="editorWidth"
				:minDimension="360"
				:maxDimension="maxEditorWidth"
				@resize="editorWidth = $event"
				@dblclick="toggleFullWidth"
			/>
			<div
				class="flex select-none items-center justify-between gap-2 border-b border-outline-gray-2 px-3 py-2"
				@dblclick="toggleFullWidth"
			>
				<div class="flex min-w-0 items-center gap-1.5">
					<span
						class="mt-1 shrink-0 font-mono text-[10px] font-bold leading-none"
						:class="getFileBadge(openFile!.path).colorClass"
					>
						{{ getFileBadge(openFile!.path).label }}
					</span>
					<span class="truncate text-sm text-ink-gray-8" :title="openFile!.path">
						{{ openFile!.path }}
						<span v-if="dirty" class="text-ink-amber-3">•</span>
					</span>
				</div>
				<div class="flex shrink-0 items-center gap-1" @dblclick.stop>
					<Button size="xs" variant="solid" :loading="saving" :disabled="!dirty" @click="save">Save</Button>
					<Button size="xs" variant="ghost" icon="lucide-trash-2" @click="removeFile" title="Delete file" />
					<Button size="xs" variant="ghost" icon="lucide-x" @click="closeFile" title="Close editor" />
				</div>
			</div>
			<div class="min-h-0 flex-1 overflow-hidden">
				<Code
					:modelValue="editorContent"
					:language="language"
					height="100%"
					maxHeight="100%"
					:emitOnChange="true"
					:borderless="true"
					:completions="vueImportCompletions"
					@update:modelValue="onEditorChange"
					@save="save"
				/>
			</div>
		</div>
	</Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from "vue"
import { useWindowSize } from "@vueuse/core"
import { Button, Dialog, FormControl, Tree, toast, Tooltip } from "frappe-ui"
import Code from "@/components/Code.vue"
import EmptyState from "@/components/EmptyState.vue"
import PanelResizer from "@/components/PanelResizer.vue"
import useStudioStore from "@/stores/studioStore"
import {
	listStudioFiles,
	readStudioFile,
	writeStudioFile,
	createStudioFile,
	deleteStudioFile,
	languageForFile,
	type StudioFileNode,
} from "@/data/studioFiles"
import { confirm } from "@/utils/helpers"
import { suppressNextViteReload } from "@/utils/viteReload"
import { vueImportCompletions } from "@/utils/vueApiCompletions"
import type { StudioApp } from "@/types/Studio/StudioApp"

const props = defineProps<{
	app: StudioApp
}>()

const store = useStudioStore()

const treeOptions = {
	rowHeight: "28px",
	indentWidth: "14px",
	showIndentationGuides: false,
	defaultCollapsed: false,
}

const tree = ref<StudioFileNode[]>([])
const loading = ref(false)
const saving = ref(false)
const openFile = ref<{ path: string; hash: string } | null>(null)
const editorContent = ref("")
const savedContent = ref("")
const showNewFileDialog = ref(false)
const newFilePath = ref("")

const location = computed(() => ({
	frappe_app: props.app.frappe_app!,
	studio_app: props.app.name,
}))
const selectedNode = ref<StudioFileNode | null>(null)
const showEditor = computed(
	() =>
		Boolean(openFile.value) &&
		store.studioLayout.showLeftPanel &&
		store.studioLayout.leftPanelActiveTab === "Code",
)

const panelLeft = computed(() => store.studioLayout.leftPanelWidth)
const EDITOR_WIDTH = 520
const editorWidth = ref(EDITOR_WIDTH)
// Cap the editor so its right edge stops at the app's right edge (it may cover the right panel,
// but never overflow the window). Recomputes as the window or left panel resizes.
const { width: viewportWidth } = useWindowSize()
const maxEditorWidth = computed(() => Math.max(360, viewportWidth.value - panelLeft.value))
const restoreWidth = ref(EDITOR_WIDTH)

watch(
	maxEditorWidth,
	(max) => {
		if (editorWidth.value > max) editorWidth.value = max
	},
	{ immediate: true },
)

// Double-click snaps to full width; double-click again restores the previous width.
function toggleFullWidth() {
	if (editorWidth.value >= maxEditorWidth.value - 1) {
		editorWidth.value = Math.min(restoreWidth.value, maxEditorWidth.value)
	} else {
		restoreWidth.value = editorWidth.value
		editorWidth.value = maxEditorWidth.value
	}
}
const dirty = computed(() => Boolean(openFile.value) && editorContent.value !== savedContent.value)
const language = computed(() => (openFile.value ? languageForFile(openFile.value.path) : "javascript"))

function getFileBadge(path: string): { label: string; colorClass: string } {
	const extension = path.slice(path.lastIndexOf(".")).toLowerCase()
	switch (extension) {
		case ".vue":
			return { label: "V", colorClass: "text-ink-green-3" }
		case ".js":
			return { label: "JS", colorClass: "text-ink-amber-3" }
		case ".ts":
			return { label: "TS", colorClass: "text-ink-blue-3" }
		case ".json":
			return { label: "{}", colorClass: "text-ink-gray-5" }
		case ".css":
			return { label: "#", colorClass: "text-ink-red-3" }
		default:
			return { label: "•", colorClass: "text-ink-gray-4" }
	}
}

const activePage = computed(() => store.activePage)
const activePagePaths = computed(() => {
	const title = activePage.value?.page_title
	if (!title) return null
	const folder = `studio_page/${scrub(title)}`
	return { folder, script: `${folder}/${scrub(title)}.ts` }
})

function scrub(text: string): string {
	return text.replaceAll(" ", "_").replaceAll("-", "_").toLowerCase()
}

function findNode(path: string | null, nodes: StudioFileNode[] = tree.value): StudioFileNode | null {
	if (!path) return null
	for (const node of nodes) {
		if (node.path === path) return node
		const found = findNode(path, node.children)
		if (found) return found
	}
	return null
}

const activePageHasScript = computed(() => Boolean(findNode(activePagePaths.value?.script ?? null)))

function openActivePageScript() {
	const scriptPath = activePagePaths.value?.script
	if (!scriptPath) return
	const scriptNode = findNode(scriptPath)
	if (scriptNode) {
		selectedNode.value = scriptNode
		openNode(scriptNode)
	} else {
		newFilePath.value = scriptPath
		showNewFileDialog.value = true
	}
}

async function loadTree() {
	loading.value = true
	try {
		tree.value = await listStudioFiles(location.value)
	} catch (error: any) {
		toast.error("Failed to load files", { description: error?.messages?.join(", ") })
	} finally {
		loading.value = false
	}
}

function onNodeClick(node: StudioFileNode, toggleCollapsed: (event: MouseEvent) => void, event: MouseEvent) {
	selectedNode.value = node
	if (node.is_folder) toggleCollapsed(event)
	else openNode(node)
}

const pathInput = ref<any>(null)
function currentFolderPath(): string {
	const node = selectedNode.value
	if (!node) return ""
	if (node.is_folder) return `${node.path}/`
	const slash = node.path.lastIndexOf("/")
	return slash === -1 ? "" : node.path.slice(0, slash + 1)
}

function openNewFileDialog() {
	newFilePath.value = currentFolderPath()
	showNewFileDialog.value = true
	nextTick(() => {
		requestAnimationFrame(() => {
			const input = pathInput.value?.$el?.querySelector?.("input") as HTMLInputElement | undefined
			if (!input) return
			input.focus()
			input.setSelectionRange(input.value.length, input.value.length)
		})
	})
}

async function openNode(node: StudioFileNode) {
	if (dirty.value) {
		const discard = await confirm("Discard unsaved changes?")
		if (!discard) return
	}
	try {
		const file = await readStudioFile(location.value, node.path)
		openFile.value = { path: file.path, hash: file.hash }
		editorContent.value = file.content
		savedContent.value = file.content
	} catch (error: any) {
		toast.error("Failed to open file", { description: error?.messages?.join(", ") })
	}
}

function onEditorChange(value: string) {
	editorContent.value = value
}

async function closeFile() {
	if (dirty.value) {
		const discard = await confirm("Discard unsaved changes?")
		if (!discard) return
	}
	openFile.value = null
}

async function save() {
	if (!openFile.value || !dirty.value) return
	saving.value = true
	try {
		const result = await writeStudioFile(
			location.value,
			openFile.value.path,
			editorContent.value,
			openFile.value.hash,
		)
		openFile.value.hash = result.hash
		savedContent.value = editorContent.value
		toast.success("Saved")
	} catch (error: any) {
		toast.error("Failed to save", { description: error?.messages?.join(", ") })
	} finally {
		saving.value = false
	}
}

async function createFile() {
	const path = newFilePath.value.trim()
	if (!path) return
	try {
		suppressNextViteReload()
		await createStudioFile(location.value, path)
		showNewFileDialog.value = false
		newFilePath.value = ""
		await loadTree()
		const newNode: StudioFileNode = {
			label: path.split("/").pop() || path,
			path,
			is_folder: false,
			children: [],
		}
		selectedNode.value = newNode
		await openNode(newNode)
	} catch (error: any) {
		toast.error("Failed to create file", { description: error?.messages?.join(", ") })
	}
}

async function removeFile() {
	if (!openFile.value) return
	if (!(await confirm(`Delete ${openFile.value.path}?`))) return
	try {
		suppressNextViteReload()
		await deleteStudioFile(location.value, openFile.value.path)
		openFile.value = null
		await loadTree()
	} catch (error: any) {
		toast.error("Failed to delete file", { description: error?.messages?.join(", ") })
	}
}

watch(
	() => props.app.name,
	() => {
		openFile.value = null
		selectedNode.value = null
		loadTree()
	},
	{ immediate: true },
)
</script>
