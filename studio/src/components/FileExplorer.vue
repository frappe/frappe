<template>
	<CollapsibleSection sectionName="Code Files">
		<div class="flex flex-col gap-3">
			<!-- File tree -->
			<div class="flex items-center justify-between">
				<span class="text-sm text-ink-gray-6">{{ app.app_name }}/studio</span>
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

			<div class="max-h-[220px] overflow-auto rounded border border-outline-gray-2 p-1">
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
							<span
								v-if="node.is_folder"
								class="size-3.5 shrink-0 text-ink-gray-5"
								:class="isCollapsed ? 'lucide-chevron-right' : 'lucide-chevron-down'"
							/>
							<span v-else class="lucide-file size-3.5 shrink-0 text-ink-gray-4" />
							<span class="truncate text-sm">{{ node.label }}</span>
						</div>
					</template>
				</Tree>
			</div>

			<!-- Editor -->
			<div v-if="openFile" class="flex flex-col gap-2">
				<div class="flex items-center justify-between">
					<span class="truncate text-sm text-ink-gray-7" :title="openFile.path">
						{{ openFile.path }}
						<span v-if="dirty" class="text-ink-gray-5">•</span>
					</span>
					<div class="flex items-center gap-1">
						<Button variant="ghost" icon="lucide-trash-2" @click="removeFile" title="Delete file" />
						<Button variant="solid" :loading="saving" :disabled="!dirty" @click="save">Save</Button>
					</div>
				</div>
				<Code
					:modelValue="editorContent"
					:language="language"
					:isFormInput="true"
					height="360px"
					maxHeight="360px"
					:emitOnChange="true"
					@update:modelValue="onEditorChange"
					@save="save"
				/>
			</div>
			<EmptyState v-else message="Select a file to edit" />
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
	</CollapsibleSection>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue"
import { Button, Dialog, FormControl, Tree, toast } from "frappe-ui"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import Code from "@/components/Code.vue"
import EmptyState from "@/components/EmptyState.vue"
import {
	listStudioFiles,
	readStudioFile,
	writeStudioFile,
	createStudioFile,
	deleteStudioFile,
	languageForFile,
	type StudioFileNode,
} from "@/data/studioFiles"
import type { StudioApp } from "@/types/Studio/StudioApp"

const props = defineProps<{
	app: StudioApp
}>()

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
const selectedPath = computed(() => openFile.value?.path)
const dirty = computed(() => Boolean(openFile.value) && editorContent.value !== savedContent.value)
const language = computed(() => (openFile.value ? languageForFile(openFile.value.path) : "javascript"))

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
	if (dirty.value && !confirm("Discard unsaved changes?")) return
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
	if (!confirm(`Delete ${openFile.value.path}?`)) return
	try {
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
