<template>
	<div class="flex flex-col gap-2">
		<!-- File tree -->
		<div class="flex items-center justify-between">
			<div class="flex flex-col gap-2">
				<span class="text-sm-medium text-ink-gray-7">{{ app?.app_name }}/studio</span>
			</div>
			<div class="flex items-center gap-1">
				<Button
					variant="ghost"
					icon="lucide-file-plus"
					@click="openNewEntryDialog('file')"
					title="New file"
				/>
				<Button
					v-if="!store.isDbApp"
					variant="ghost"
					icon="lucide-folder-plus"
					@click="openNewEntryDialog('folder')"
					title="New folder"
				/>
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
			:disabled="loading"
			class="flex w-full items-center gap-2 rounded-4 border border-outline-gray-2 px-2 py-1.5 text-left hover:bg-surface-gray-2"
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

		<div ref="treeContainer" class="overflow-auto rounded-4">
			<EmptyState v-if="!loading && !tree.length" message="No code files yet" />
			<Tree :nodes="tree" nodeKey="path" guides="none" :style="treeStyle">
				<template #item="{ node, expanded, toggle }">
					<div
						class="flex h-7 flex-1 cursor-pointer select-none items-center gap-1 rounded-4 px-1 outline-none"
						:class="
							selectedNode?.path === node.path
								? 'bg-surface-gray-3 text-ink-gray-9'
								: 'text-ink-gray-7 hover:bg-surface-gray-2'
						"
						tabindex="0"
						@click.stop="onNodeClick(node, toggle)"
						@contextmenu.prevent.stop="openContextMenu($event, node)"
						@keydown.enter.prevent.stop="startRename(node)"
						@keydown.f2.prevent.stop="startRename(node)"
					>
						<div class="mt-[1.25px] flex w-5 shrink-0 flex-col items-center justify-center">
							<span
								v-if="node.is_folder"
								class="size-3.5 items-center text-ink-gray-5"
								:class="expanded ? 'lucide-chevron-down' : 'lucide-chevron-right'"
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
							:data-file-label="node.path"
							class="min-w-0 flex-1 rounded-4 text-sm outline-none"
							:class="[
								node.path === activePagePaths?.folder ? 'font-medium text-ink-gray-9' : '',
								editingPath === node.path
									? 'select-text !overflow-visible whitespace-nowrap bg-surface-base px-1 ring-1 ring-outline-gray-3'
									: '',
							]"
							:contenteditable="editingPath === node.path"
							@click="onLabelClick($event, node)"
							@keydown.enter.stop.prevent="($event.target as HTMLElement).blur()"
							@keydown.escape.stop.prevent="cancelRename($event, node)"
							@blur="commitRename($event, node)"
						>
							{{ node.label }}
						</div>
						<Tooltip
							v-if="node.path === activePagePaths?.folder"
							text="Currently editing this page"
							side="right"
						>
							<span class="ml-1 mt-0.5 shrink-0 text-[8px] text-ink-blue-5">●</span>
						</Tooltip>
					</div>
				</template>
			</Tree>
		</div>
	</div>

	<Dialog
		v-model="showNewEntryDialog"
		:title="newEntryType === 'folder' ? 'New Folder' : 'New File'"
		width="md"
	>
		<template #default>
			<FormControl
				ref="pathInput"
				type="text"
				variant="outline"
				:label="newEntryType === 'folder' ? 'Folder path' : 'File path'"
				:description="newEntryDescription"
				:placeholder="
					newEntryType === 'folder'
						? 'composables'
						: `composables/useThing.${store.isDbApp ? 'js' : 'ts'}`
				"
				v-model="newEntryPath"
				@keyup.enter="createEntry"
			/>
		</template>
		<template #actions>
			<Button variant="solid" label="Create" class="w-full" @click="createEntry" />
		</template>
	</Dialog>

	<Teleport to="body">
		<ContextMenu ref="contextMenuRef" :options="contextMenuOptions" @select="onContextMenuSelect" />
	</Teleport>

	<CodeEditorDock
		:open="Boolean(openFile)"
		:modelValue="editorContent"
		:language="language"
		:readonly="openFileReadOnly"
		:completions="pageScriptCompletions"
		@update:modelValue="onEditorChange"
		@save="save"
	>
		<template #title>
			<span
				class="mt-0.5 shrink-0 font-mono text-[10px] font-bold leading-none"
				:class="getFileBadge(openFile!.path).colorClass"
			>
				{{ getFileBadge(openFile!.path).label }}
			</span>
			<span class="truncate text-sm text-ink-gray-8" :title="openFile!.path">
				{{ openFile!.path }}
				<span v-if="dirty" class="text-ink-amber-5">•</span>
			</span>
			<span v-if="openFileReadOnly" class="shrink-0 text-xs text-ink-gray-4">read-only</span>
		</template>
		<template #actions>
			<Popover v-if="isPageScript" side="bottom" align="end" :offset="6" bare>
				<template #trigger>
					<Button size="xs" variant="ghost" icon="lucide-circle-help" title="How to write the page script" />
				</template>
				<div class="max-w-sm rounded-4 border border-outline-gray-2 bg-surface-base p-3 shadow-lg">
					<PageScriptHelp />
				</div>
			</Popover>
			<template v-if="!openFileReadOnly">
				<Button size="xs" variant="ghost" icon="lucide-trash-2" @click="removeFile" title="Delete file" />
				<Button size="xs" variant="solid" :loading="saving" :disabled="!dirty" @click="save">Save</Button>
			</template>
			<Button size="xs" variant="ghost" icon="lucide-x" @click="closeFile" title="Close editor" />
		</template>

		<template #banner>
			<ErrorMessage
				v-if="scriptError || (pageScope.pageScriptError && isEditingActivePageScript)"
				class="border-b border-outline-gray-2 px-3 py-2"
				:message="scriptError || `Error: ${pageScope.pageScriptError}`"
			/>
		</template>
	</CodeEditorDock>
</template>

<script setup lang="ts">
import { ref, computed, inject, watch, nextTick, onMounted, onBeforeUnmount } from "vue"
import { useStorage } from "@vueuse/core"
import { Button, Dialog, ErrorMessage, FormControl, Popover, Tree, toast, Tooltip } from "frappe-ui"
import CodeEditorDock from "@/components/CodeEditorDock.vue"
import ContextMenu from "@/components/ContextMenu.vue"
import EmptyState from "@/components/EmptyState.vue"
import PageScriptHelp from "@/components/PageScriptHelp.vue"
import useStudioStore from "@/stores/studioStore"
import { usePageScope } from "@/stores/codeStore"
import {
	listStudioFiles,
	readStudioFile,
	writeStudioFile,
	createStudioFile,
	createStudioFolder,
	renameStudioFile,
	deleteStudioFile,
	languageForFile,
	resolveScriptPath,
	type StudioFileNode,
} from "@/data/studioFiles"
import { checkAppScript } from "@/browserRuntime/appRuntime"
import { confirm } from "@/utils/helpers"
import { PAGE_SCRIPT_BOILERPLATE } from "@/utils/constants"
import { pageScriptCompletions } from "@/utils/completions/pageScriptCompletions"
import type { ContextMenuOption } from "@/types"

const store = useStudioStore()
const pageScope = usePageScope()
const app = computed(() => store.activeApp)

const treeStyle = {
	"--tree-row-height": "28px",
	"--tree-indent": "14px",
}

const location = computed(() => ({
	frappe_app: app.value?.frappe_app ?? "",
	studio_app: app.value?.name ?? "",
}))

// -- File tree --
const tree = ref<StudioFileNode[]>([])
const loading = ref(false)

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

// -- Node selection --
const selectedNode = ref<StudioFileNode | null>(null)

function onNodeClick(node: StudioFileNode, toggle: () => void) {
	selectedNode.value = node
	if (node.is_folder) toggle()
	else openNode(node)
}

// -- Active page --
const activePage = computed(() => store.activePage)

function scrub(text: string): string {
	return text.replaceAll(" ", "_").replaceAll("-", "_").toLowerCase()
}

const activePagePaths = computed(() => {
	const title = activePage.value?.page_title
	if (!title) return null
	const folder = `studio_page/${scrub(title)}`
	const stem = `${folder}/${scrub(title)}`
	const existing = [`${stem}.ts`, `${stem}.js`].filter((path) => findNode(path))
	return { folder, stem, existing }
})

function findNode(path: string | null, nodes: StudioFileNode[] = tree.value): StudioFileNode | null {
	if (!path) return null
	for (const node of nodes) {
		if (node.path === path) return node
		const found = findNode(path, node.children)
		if (found) return found
	}
	return null
}

const activePageHasScript = computed(() => Boolean(activePagePaths.value?.existing.length))

function openActivePageScript() {
	const paths = activePagePaths.value
	if (!paths) return
	try {
		openOrCreateFile(resolveScriptPath(paths.stem, paths.existing, store.isDbApp))
	} catch (error: any) {
		toast.error("Failed to open the page script", { description: error.message })
	}
}

function openOrCreateFile(path: string) {
	const node = findNode(path)
	if (node) {
		selectedNode.value = node
		openNode(node)
	} else {
		newEntryType.value = "file"
		newEntryPath.value = path
		showNewEntryDialog.value = true
		focusFormInput(pathInput)
	}
}

// -- Open / read file --
const openFile = ref<{ path: string; hash: string } | null>(null)
const editorContent = ref("")
const savedContent = ref("")
const dirty = computed(() => Boolean(openFile.value) && editorContent.value !== savedContent.value)
const language = computed(() => (openFile.value ? languageForFile(openFile.value.path) : "javascript"))

const isEditingActivePageScript = computed(() =>
	Boolean(openFile.value && activePagePaths.value?.existing.includes(openFile.value.path)),
)

// Page scripts use setup(context), so show their starter code, help and syntax errors.
const isPageScript = computed(() => Boolean(openFile.value) && isPageScriptPath(openFile.value!.path))
const scriptError = ref<string | null>(null)

// the app doc exports to <scrub(app)>.json at the studio root
const appJsonPath = computed(() => `${scrub(app.value?.name ?? "")}.json`)
const isExportDocFile = (path: string) =>
	path.toLowerCase().endsWith(".json") &&
	(path.startsWith("studio_page/") || path.startsWith("studio_components/") || path === appJsonPath.value)
const isExportFolder = (path: string) =>
	path === "studio_page" || path === "studio_components" || /^studio_page\/[^/]+$/.test(path)
const isProtectedNode = (node: StudioFileNode) =>
	node.is_folder ? isExportFolder(node.path) : isExportDocFile(node.path)

const openFileReadOnly = computed(() => Boolean(openFile.value) && isExportDocFile(openFile.value!.path))

function getFileBadge(path: string): { label: string; colorClass: string } {
	const extension = path.slice(path.lastIndexOf(".")).toLowerCase()
	switch (extension) {
		case ".vue":
			return { label: "V", colorClass: "text-ink-green-5" }
		case ".js":
			return { label: "JS", colorClass: "text-ink-orange-5" }
		case ".ts":
			return { label: "TS", colorClass: "text-ink-blue-6" }
		case ".json":
			return { label: "{}", colorClass: "text-ink-gray-5" }
		case ".css":
			return { label: "#", colorClass: "text-ink-red-5" }
		default:
			return { label: "•", colorClass: "text-ink-gray-4" }
	}
}

async function openNode(node: StudioFileNode) {
	if (node.path === "router.js" || node.path === "router.ts") return openRouterEditor()
	if (dirty.value) {
		const discard = await confirm("Discard unsaved changes?")
		if (!discard) return
	}
	try {
		const file = await readStudioFile(location.value, node.path)
		openFile.value = { path: file.path, hash: file.hash }
		// Start empty page scripts with the required setup(context) module structure.
		editorContent.value =
			!file.content && isPageScriptPath(file.path) ? PAGE_SCRIPT_BOILERPLATE : file.content
		savedContent.value = file.content
	} catch (error: any) {
		toast.error("Failed to open file", { description: error?.messages?.join(", ") })
	}
}

// the router editor owns the router file: its completions, page-name warning and help live there
function openRouterEditor() {
	store.studioLayout.leftPanelActiveTab = "Pages"
	store.showRouterEditor = true
}

function onEditorChange(value: string) {
	// Blur also emits the current text. Ignore unchanged text to preserve Save's validation error.
	if (value !== editorContent.value) scriptError.value = null
	editorContent.value = value
}

async function closeFile() {
	if (dirty.value) {
		const discard = await confirm("Discard unsaved changes?")
		if (!discard) return
	}
	openFile.value = null
}

// -- Save --
const saving = ref(false)

async function save() {
	if (!openFile.value || !dirty.value || openFileReadOnly.value) return
	// Reject syntax errors before they prevent page setup from creating bindings.
	if (isPageScript.value) {
		const syntaxError = await checkAppScript(editorContent.value, openFile.value.path, store.isDbApp)
		if (syntaxError) {
			const hint = editorContent.value.includes("{{")
				? " Use expressions directly in scripts, not {{ }} interpolation."
				: ""
			scriptError.value = `${syntaxError}.${hint}`
			return
		}
	}
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
		// Refresh stored source immediately instead of waiting for its realtime event.
		if (store.isDbApp) store.refreshAppFiles()
		// Page scripts update their owning page record, so reload the active page's setup.
		if (isEditingActivePageScript.value) store.reloadActivePageScript()
	} catch (error: any) {
		toast.error("Failed to save", { description: error?.messages?.join(", ") })
	} finally {
		saving.value = false
	}
}

// -- Create new file/folder --
const showNewEntryDialog = ref(false)
const newEntryPath = ref("")
const newEntryType = ref<"file" | "folder">("file")
// A database app's source runs as it is, so TypeScript and .vue files need a repository app.
const allowedExtensions = computed(() =>
	store.isDbApp ? ".js, .json, .css" : ".ts, .js, .vue, .json, .css",
)
const newEntryDescription = computed(() =>
	newEntryType.value === "folder"
		? `Relative to studio/${app.value?.app_name}`
		: `Relative to studio/${app.value?.app_name}. Allowed: ${allowedExtensions.value}`,
)
const pathInput = ref<any>(null)
const treeContainer = ref<HTMLElement | null>(null)

function currentFolderPath(): string {
	const node = selectedNode.value
	if (!node) return ""
	if (node.is_folder) return `${node.path}/`
	const slash = node.path.lastIndexOf("/")
	return slash === -1 ? "" : node.path.slice(0, slash + 1)
}

function openNewEntryDialog(type: "file" | "folder") {
	newEntryType.value = type
	newEntryPath.value = currentFolderPath()
	showNewEntryDialog.value = true
	focusFormInput(pathInput)
}

// Focus a FormControl's <input> once the dialog has rendered, optionally selecting [start, end).
function focusFormInput(formRef: { value: any }, start?: number, end?: number) {
	nextTick(() => {
		requestAnimationFrame(() => {
			const input = formRef.value?.$el?.querySelector?.("input") as HTMLInputElement | undefined
			if (!input) return
			input.focus()
			input.setSelectionRange(start ?? input.value.length, end ?? input.value.length)
		})
	})
}

function isPageScriptPath(path: string): boolean {
	const match = path.match(/^studio_page\/([^/]+)\/([^/]+)\.(?:js|ts)$/)
	return Boolean(match && match[1] === match[2])
}

async function createEntry() {
	const path = newEntryPath.value.trim().replace(/\/+$/, "")
	if (!path) return
	const isFolder = newEntryType.value === "folder"
	try {
		if (isFolder) {
			await createStudioFolder(location.value, path)
		} else {
			await createStudioFile(location.value, path)
			if (isPageScriptPath(path)) {
				await writeStudioFile(location.value, path, PAGE_SCRIPT_BOILERPLATE)
			}
		}
		showNewEntryDialog.value = false
		newEntryPath.value = ""
		await loadTree()
		const newNode: StudioFileNode = {
			label: path.split("/").pop() || path,
			path,
			is_folder: isFolder,
			children: [],
		}
		selectedNode.value = findNode(path) ?? newNode
		if (!isFolder) await openNode(newNode)
	} catch (error: any) {
		toast.error(`Failed to create ${isFolder ? "folder" : "file"}`, {
			description: error?.messages?.join(", "),
		})
	}
}

// -- Context menu --
const contextMenuRef = ref<InstanceType<typeof ContextMenu> | null>(null)
const contextMenuNode = ref<StudioFileNode | null>(null)

const contextMenuOptions = computed<ContextMenuOption[]>(() => {
	const node = contextMenuNode.value
	if (!node) return []
	// Studio-generated files and folders cannot be renamed or deleted here.
	// A page script can be cleared; rename its owning page to change the script's name.
	const options: ContextMenuOption[] = isProtectedNode(node)
		? []
		: [
				...(isPageScriptPath(node.path) ? [] : [{ label: "Rename", action: () => startRename(node) }]),
				{
					label: isPageScriptPath(node.path) ? "Clear" : "Delete",
					action: () => deleteNode(node),
					theme: "red",
				},
			]
	if (!node.is_folder && node.path.endsWith(".vue")) {
		const componentName = node.label.replace(/\.vue$/i, "")
		options.unshift({ label: "Go to Component", action: () => store.navigateToVueComponent(componentName) })
	}
	return options
})

function openContextMenu(event: MouseEvent, node: StudioFileNode) {
	selectedNode.value = node
	contextMenuNode.value = node
	if (!contextMenuOptions.value.length) return // read-only file: nothing to offer
	contextMenuRef.value?.show(event.pageX, event.pageY)
}

function closeContextMenu() {
	contextMenuRef.value?.hide()
}

function onContextMenuSelect(action: CallableFunction) {
	action()
	closeContextMenu()
}

// cross-panel navigation
watch(
	() => store.selectedVueFile,
	async (path) => {
		if (!path) return
		store.selectedVueFile = null
		// tree may still be loading on first mount — wait for it
		if (loading.value) {
			const stop = watch(loading, async (isLoading) => {
				if (isLoading) return
				stop()
				openOrCreateFile(path)
			})
		} else {
			openOrCreateFile(path)
		}
	},
)

// -- Rename --
const editingPath = ref<string | null>(null)

function startRename(node: StudioFileNode) {
	closeContextMenu()
	// A page script is named after its page, so only a retitle may rename it.
	if (isProtectedNode(node) || isPageScriptPath(node.path)) return
	editingPath.value = node.path
	nextTick(() => requestAnimationFrame(() => focusLabel(node)))
}

function focusLabel(node: StudioFileNode) {
	const el = treeContainer.value?.querySelector<HTMLElement>(`[data-file-label="${node.path}"]`)
	const textNode = el?.firstChild
	if (!el || !textNode) return
	el.focus()
	// select the basename minus a file's extension, so the user can just retype the name
	const dot = node.label.lastIndexOf(".")
	const end = !node.is_folder && dot > 0 ? dot : node.label.length
	const range = document.createRange()
	range.setStart(textNode, 0)
	range.setEnd(textNode, Math.min(end, textNode.textContent?.length ?? 0))
	const selection = window.getSelection()
	selection?.removeAllRanges()
	selection?.addRange(range)
}

// Commit on blur (Enter blurs the field). The rename only changes the basename; the folder stays.
async function commitRename(event: Event, node: StudioFileNode) {
	if (editingPath.value !== node.path) return // already cancelled
	editingPath.value = null
	const target = event.target as HTMLElement
	const newLabel = (target.innerText || "").trim()
	if (!newLabel || newLabel === node.label) {
		target.innerText = node.label // discard partial/empty edits
		return
	}
	const newPath = parentDir(node.path) + newLabel
	try {
		await renameStudioFile(location.value, node.path, newPath)
		remapOpenFile(node.path, newPath, node.is_folder)
		await loadTree()
		selectedNode.value = findNode(newPath)
	} catch (error: any) {
		toast.error("Failed to rename", { description: error?.messages?.join(", ") })
		await loadTree() // restore the original label
	}
}

function cancelRename(event: Event, node: StudioFileNode) {
	editingPath.value = null
	;(event.target as HTMLElement).innerText = node.label
	;(event.target as HTMLElement).blur()
}

// Don't open the file when clicking the label to place the caret mid-rename.
function onLabelClick(event: MouseEvent, node: StudioFileNode) {
	if (editingPath.value === node.path) event.stopPropagation()
}

function parentDir(path: string): string {
	const slash = path.lastIndexOf("/")
	return slash === -1 ? "" : path.slice(0, slash + 1)
}

// Keep the editor pointed at the open file after it (or a folder containing it) is renamed.
function remapOpenFile(oldPath: string, newPath: string, isFolder: boolean) {
	if (!openFile.value) return
	if (openFile.value.path === oldPath) {
		openFile.value.path = newPath
	} else if (isFolder && openFile.value.path.startsWith(`${oldPath}/`)) {
		openFile.value.path = newPath + openFile.value.path.slice(oldPath.length)
	}
}

// -- Delete --
async function deleteNode(node: StudioFileNode) {
	if (isProtectedNode(node)) return // export-managed, can't delete
	const message = node.is_folder
		? `Delete ${node.path} and everything inside it?`
		: isPageScriptPath(node.path)
			? `Clear ${node.path}? The page keeps its empty script.`
			: `Delete ${node.path}?`
	if (!(await confirm(message))) return
	try {
		await deleteStudioFile(location.value, node.path)
		if (openFileIsUnder(node.path, node.is_folder)) openFile.value = null
		if (selectedNode.value?.path === node.path) selectedNode.value = null
		await loadTree()
	} catch (error: any) {
		toast.error("Failed to delete", { description: error?.messages?.join(", ") })
	}
}

function removeFile() {
	if (!openFile.value) return
	deleteNode({ label: "", path: openFile.value.path, is_folder: false, children: [] })
}

function openFileIsUnder(path: string, isFolder: boolean): boolean {
	if (!openFile.value) return false
	return openFile.value.path === path || (isFolder && openFile.value.path.startsWith(`${path}/`))
}

// remember last opened file
const lastOpenFiles = useStorage<Record<string, string>>("studioOpenFiles", {})
watch(
	() => openFile.value?.path,
	(path) => {
		const appName = app.value?.name
		if (!appName) return
		if (path) lastOpenFiles.value[appName] = path
		else delete lastOpenFiles.value[appName]
	},
)

watch(
	() => app.value?.name,
	async (appName) => {
		const remembered = appName ? lastOpenFiles.value[appName] : undefined
		openFile.value = null
		selectedNode.value = null
		try {
			await loadTree()
			reopenLastFile(remembered)
		} finally {
			if (appName && remembered && !openFile.value) lastOpenFiles.value[appName] = remembered
		}
	},
	{ immediate: true },
)

function reopenLastFile(path: string | undefined) {
	const node = path ? findNode(path) : null
	if (!node) return
	selectedNode.value = node
	openNode(node)
}

async function onStudioFilesChanged() {
	await loadTree()
	if (openFile.value && !findNode(openFile.value.path)) openFile.value = null
	if (selectedNode.value && !findNode(selectedNode.value.path)) selectedNode.value = null
}

// The open file was edited on disk (e.g. in another editor). Re-read it unless the user has
// unsaved changes here — then save()'s hash check guards the conflict instead.
async function onStudioFileChanged({ path }: { path: string }) {
	if (!openFile.value || dirty.value) return
	if (path !== `${location.value.studio_app}/${openFile.value.path}`) return
	try {
		const file = await readStudioFile(location.value, openFile.value.path)
		openFile.value.hash = file.hash
		editorContent.value = file.content
		savedContent.value = file.content
	} catch {
		// file vanished between events; the structure handler will reconcile the tree
	}
}

// Stored files have no Vite watcher. Realtime events refresh the tree and any open file that changed.
const socket = inject<any>("socket")

async function onAppFileChange(info: { doctype: string; name: string; studio_app: string }) {
	if (info?.doctype !== "Studio App File" || !store.isDbApp) return
	if (info.studio_app !== location.value.studio_app) return
	await onStudioFilesChanged()
	if (openFile.value && info.name === openFile.value.path) {
		await onStudioFileChanged({ path: `${info.studio_app}/${info.name}` })
	}
}

onMounted(() => {
	import.meta.hot?.on("studio:files-changed", onStudioFilesChanged)
	import.meta.hot?.on("studio:file-changed", onStudioFileChanged)
	socket?.on("studio_doc_update", onAppFileChange)
})
onBeforeUnmount(() => {
	import.meta.hot?.off("studio:files-changed", onStudioFilesChanged)
	import.meta.hot?.off("studio:file-changed", onStudioFileChanged)
	socket?.off("studio_doc_update", onAppFileChange)
})
</script>
