<template>
	<div class="flex flex-col gap-3">
		<!-- File tree -->
		<div class="flex items-center justify-between">
			<div class="flex flex-col gap-2">
				<span class="text-sm font-semibold text-ink-gray-6">{{ app.app_name }}/studio</span>
			</div>
			<div class="flex items-center gap-1">
				<Button variant="ghost" icon="lucide-plus" @click="showNewFileDialog = true" title="New file" />
				<Button
					variant="ghost"
					icon="lucide-refresh-cw"
					:loading="loading"
					@click="loadTree"
					title="Refresh"
				/>
			</div>
		</div>

		<div class="overflow-auto rounded">
			<EmptyState v-if="!loading && !tree.length" message="No code files yet" />
			<Tree v-for="node in tree" :key="node.path" :node="node" nodeKey="path" :options="treeOptions">
				<template #node="{ node, isCollapsed, toggleCollapsed }">
					<div
						class="flex h-7 cursor-pointer items-center gap-1 rounded px-1"
						:class="
							selectedPath === node.path
								? 'bg-surface-gray-3 text-ink-gray-9'
								: 'text-ink-gray-7 hover:bg-surface-gray-2'
						"
						@click="onNodeClick(node, toggleCollapsed)"
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
						<div class="truncate text-sm">{{ node.label }}</div>
					</div>
				</template>
			</Tree>
		</div>
	</div>

	<Dialog v-model="showNewFileDialog" title="New File" width="md">
		<template #default>
			<FormControl
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
				:maxDimension="1200"
				@resize="editorWidth = $event"
			/>
			<div class="flex items-center justify-between gap-2 border-b border-outline-gray-2 px-3 py-2">
				<span class="truncate text-sm text-ink-gray-8" :title="openFile!.path">
					{{ openFile!.path }}
					<span v-if="dirty" class="text-ink-amber-3">•</span>
				</span>
				<div class="flex shrink-0 items-center gap-1">
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
					@update:modelValue="onEditorChange"
					@save="save"
				/>
			</div>
		</div>
	</Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue"
import { Button, Dialog, FormControl, Tree, toast } from "frappe-ui"
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
const editorWidth = ref(520)

const location = computed(() => ({
	frappe_app: props.app.frappe_app!,
	studio_app: props.app.name,
}))
const selectedPath = computed(() => openFile.value?.path)
// The editor belongs to the Code tab: keep it docked only while that tab is the visible left panel.
const showEditor = computed(
	() =>
		Boolean(openFile.value) &&
		store.studioLayout.showLeftPanel &&
		store.studioLayout.leftPanelActiveTab === "Code",
)
// dock the editor flush against the right edge of the left panel
const panelLeft = computed(() => store.studioLayout.leftPanelWidth)
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

function onNodeClick(node: StudioFileNode, toggleCollapsed: () => void) {
	if (node.is_folder) toggleCollapsed()
	else openNode(node)
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
		await openNode({ label: path, path, is_folder: false, children: [] })
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
		loadTree()
	},
	{ immediate: true },
)
</script>
