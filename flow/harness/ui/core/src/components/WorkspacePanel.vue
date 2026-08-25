<template>
	<Transition name="flow-backdrop">
		<button
			v-if="workspace.open && !workspace.maximized"
			class="fixed inset-0 z-20 bg-black/30 md:hidden"
			aria-label="Close panel"
			@click="flow.setWorkspaceOpen(false)"
		/>
	</Transition>
	<aside
		v-if="workspace.open"
		class="flex flex-col border-l border-outline-gray-1 bg-surface-white"
		:class="
			workspace.maximized
				? 'fixed inset-0 z-40'
				: 'fixed inset-y-0 right-0 z-30 w-[var(--workspace-w)] max-w-full flex-none md:relative'
		"
		:style="workspace.maximized ? {} : { '--workspace-w': width + 'px' }"
	>
		<div
			v-if="!workspace.maximized"
			class="absolute inset-y-0 left-0 z-10 hidden w-1 cursor-col-resize hover:bg-[--outline-gray-2] active:bg-[--outline-gray-3] md:block"
			title="Drag to resize · double-click to reset"
			@pointerdown="startResize"
			@dblclick="resetWidth"
		/>

		<!-- panel-level tab strip: one tab per open item of any kind (editor today,
		     browser/terminal later) — kind-specific chrome lives below, not here -->
		<div class="flex h-9 flex-none items-stretch bg-surface-white">
			<div class="flow-tab-strip flex min-w-0 items-center gap-1 overflow-x-auto px-1.5" role="tablist">
				<div
					v-for="tab in workspace.tabs"
					:key="tab.path"
					role="tab"
					tabindex="0"
					:aria-selected="tab.path === workspace.active"
					class="group flex h-7 w-40 flex-none cursor-pointer items-center gap-1.5 rounded-md pl-2.5 pr-1 text-xs"
					:class="
						tab.path === workspace.active
							? 'bg-surface-gray-2 text-ink-gray-9'
							: 'text-ink-gray-5 hover:bg-surface-gray-1 hover:text-ink-gray-8'
					"
					:title="tab.path"
					@click="flow.selectFile(tab.path)"
					@keydown.enter.prevent="flow.selectFile(tab.path)"
				>
					<span class="min-w-0 flex-1 truncate text-left">{{ tab.name }}</span>
					<button
						class="grid h-4 w-4 flex-none place-items-center rounded text-ink-gray-4 hover:bg-surface-gray-3 hover:text-ink-gray-8"
						:class="tab.path === workspace.active || tab.dirty ? '' : 'opacity-0 group-hover:opacity-100'"
						:title="tab.dirty ? 'Unsaved changes — close file' : 'Close file'"
						@click.stop="requestClose(tab)"
					>
						<span v-if="tab.dirty" class="flow-dirty-dot h-2 w-2 rounded-full bg-ink-gray-6" />
						<FeatherIcon name="x" class="h-3 w-3" :class="tab.dirty ? 'flow-dirty-x hidden' : ''" />
					</button>
				</div>
			</div>
			<span class="flex-1" />
			<button
				class="flow-icon-btn my-1 flex-none self-center"
				:title="workspace.maximized ? 'Exit full screen' : 'Full screen'"
				@click="flow.toggleWorkspaceMaximized()"
			>
				<FeatherIcon :name="workspace.maximized ? 'minimize-2' : 'maximize-2'" class="h-3.5 w-3.5" />
			</button>
			<button class="flow-icon-btn my-1 mr-1 flex-none self-center" title="Close panel" @click="flow.setWorkspaceOpen(false)">
				<FeatherIcon name="x" class="h-3.5 w-3.5" />
			</button>
		</div>

		<!-- kind-specific body; only the editor kind exists so far -->
		<div v-if="activeTab?.kind === 'editor'" class="flex min-h-0 flex-1 flex-col">
			<div class="flex h-10 flex-none items-center gap-2 border-b border-outline-gray-1 px-2.5">
				<Breadcrumbs class="flow-crumbs min-w-0" :items="crumbs" />
				<span class="flex-1" />
				<Button
					v-if="activeTab.dirty"
					variant="ghost"
					size="sm"
					class="flex-none"
					title="Save (⌘S)"
					@click="save"
				>
					Save
				</Button>
				<Button
					variant="outline"
					size="sm"
					class="flex-none"
					:class="explorerOpen ? '!bg-surface-gray-3' : ''"
					:title="explorerOpen ? 'Hide files' : 'Show files'"
					:aria-pressed="explorerOpen"
					@click="toggleExplorer"
				>
					<template #icon>
						<FeatherIcon name="folder" class="h-4 w-4" />
					</template>
				</Button>
			</div>

			<!-- the files bar opens below the header, beside the editor -->
			<div class="flex min-h-0 flex-1">
				<div class="flex min-w-0 flex-1 flex-col">
					<div
						v-if="activeTab.error"
						class="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center"
					>
						<span class="text-xs text-ink-gray-5">{{ activeTab.error }}</span>
						<button class="flow-btn-secondary" @click="flow.openFile(activeTab.path)">Retry</button>
					</div>
					<div
						v-else-if="activeTab.content == null"
						class="flex flex-1 items-center justify-center text-xs text-ink-gray-4"
					>
						Loading…
					</div>
					<div v-show="!activeTab.error && activeTab.content != null" ref="editorEl" class="min-h-0 flex-1" />
				</div>

				<div
					v-show="explorerOpen"
					class="relative flex flex-none flex-col border-l border-outline-gray-1"
					:style="{ width: explorerWidth + 'px' }"
				>
					<div class="flex-none px-1.5 pt-1.5">
						<div
							class="flex h-8 items-center gap-2 rounded-md border border-outline-gray-2 bg-surface-white px-2 text-ink-gray-5 transition-colors focus-within:border-outline-gray-3"
						>
							<FeatherIcon name="search" class="h-3.5 w-3.5 flex-none" />
							<input
								v-model="fileQuery"
								placeholder="Search files"
								spellcheck="false"
								class="h-full w-full min-w-0 border-0 bg-transparent p-0 text-xs text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
							/>
							<button
								v-if="fileQuery"
								class="grid h-4 w-4 flex-none place-items-center rounded text-ink-gray-4 hover:text-ink-gray-8"
								title="Clear"
								@click="fileQuery = ''"
							>
								<FeatherIcon name="x" class="h-3 w-3" />
							</button>
						</div>
					</div>
					<div class="min-h-0 flex-1 overflow-y-auto px-1.5 py-1.5">
						<!-- searching: a pruned tree of matches only, all branches open -->
						<template v-if="searchActive">
							<div v-if="searchMatches === null" class="px-1.5 py-2 text-2xs text-ink-gray-4">
								Searching…
							</div>
							<template v-else>
								<div
									v-for="row in searchRows"
									:key="row.path"
									:role="row.type === 'file' ? 'button' : undefined"
									:tabindex="row.type === 'file' ? 0 : undefined"
									class="relative flex items-center gap-1.5 rounded py-[5px] pr-1.5 text-sm"
									:class="
										row.type === 'file'
											? 'cursor-pointer text-ink-gray-8 hover:bg-surface-gray-2'
											: 'text-ink-gray-8'
									"
									:style="{ paddingLeft: row.depth * 16 + 8 + 'px' }"
									:title="row.path"
									@click="row.type === 'file' && flow.openFile(row.path)"
									@keydown.enter.prevent="row.type === 'file' && flow.openFile(row.path)"
								>
									<span
										v-for="level in row.depth"
										:key="level"
										class="pointer-events-none absolute inset-y-0 w-px bg-[--outline-gray-1]"
										:style="{ left: (level - 1) * 16 + 16 + 'px' }"
									/>
									<span class="grid h-4 w-4 flex-none place-items-center">
										<FeatherIcon
											:name="row.type === 'dir' ? 'chevron-down' : 'file'"
											class="h-3.5 w-3.5 text-ink-gray-5"
										/>
									</span>
									<span class="min-w-0 truncate">{{ row.name }}</span>
								</div>
								<div v-if="!searchRows.length" class="px-1.5 py-2 text-2xs text-ink-gray-4">
									No matches
								</div>
								<div v-else-if="searchTruncated" class="px-1.5 py-2 text-2xs text-ink-gray-4">
									More matches not shown — narrow the search
								</div>
							</template>
						</template>
						<template v-else-if="rootDir">
							<FileTree v-for="entry in rootEntries" :key="entry.name" :entry="entry" :dir="rootDir" />
							<div v-if="!rootEntries.length" class="px-1.5 py-2 text-2xs text-ink-gray-4">
								Empty folder
							</div>
						</template>
					</div>
					<div
						class="absolute inset-y-0 left-0 z-10 w-1 cursor-col-resize hover:bg-[--outline-gray-2] active:bg-[--outline-gray-3]"
						title="Drag to resize"
						@pointerdown="startExplorerResize"
					/>
				</div>
			</div>
		</div>
		<div v-else class="flex flex-1 items-center justify-center text-xs text-ink-gray-4">
			No file open
		</div>
	</aside>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, ref, watch } from "vue"
import Breadcrumbs from "frappe-ui/src/components/Breadcrumbs/Breadcrumbs.vue"
import Button from "frappe-ui/src/components/Button/Button.vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"
import { dialog } from "frappe-ui/src/utils/dialog"

import { useDebouncedValue } from "../debounce.js"
import { compactDisplayText } from "../transcript.js"
import FileTree from "./FileTree.vue"

const flow = inject("flow")
const workspace = computed(() => flow.state.workspace)
const cwd = computed(() => flow.state.session?.config?.cwd ?? null)
const activeTab = computed(
	() => workspace.value.tabs.find((tab) => tab.path === workspace.value.active) ?? null,
)

const crumbs = computed(() => {
	if (!activeTab.value) return []
	return compactDisplayText(activeTab.value.path, cwd.value)
		.split("/")
		.filter(Boolean)
		.map((label) => ({ label }))
})

const explorerOpen = ref(false)
const rootDir = ref(null)
const rootEntries = ref(null)

// Search runs server-side (recursive, pruned to matches); the result renders
// as a fully opened tree of only the branches that contain matches. Clearing
// the query falls back to the normal lazy tree with its manual expansion.
const fileQuery = ref("")
const debouncedFileQuery = useDebouncedValue(fileQuery, 200)
const searchActive = computed(() => debouncedFileQuery.value.trim() !== "")
const searchRoot = ref(null)
const searchMatches = ref(null) // null while a search is in flight
const searchTruncated = ref(false)

watch(debouncedFileQuery, async (raw) => {
	const query = raw.trim()
	if (!query) {
		searchMatches.value = null // reset, so the next search shows its own state
		return
	}
	// Previous results stay rendered while the new search is in flight —
	// blanking between keystrokes is what makes the list flicker. Stable row
	// keys (paths) then let Vue patch only the rows that actually changed.
	const data = await flow.searchFiles(query)
	if (debouncedFileQuery.value.trim() !== query) return // stale response
	searchRoot.value = data?.path ?? null
	searchMatches.value = data?.matches ?? []
	searchTruncated.value = data?.truncated ?? false
})

const searchRows = computed(() => {
	if (!searchMatches.value?.length || !searchRoot.value) return []
	const tree = { dirs: new Map(), files: [] }
	for (const rel of searchMatches.value) {
		const parts = rel.split("/")
		let node = tree
		for (const part of parts.slice(0, -1)) {
			if (!node.dirs.has(part)) node.dirs.set(part, { dirs: new Map(), files: [] })
			node = node.dirs.get(part)
		}
		node.files.push(parts.at(-1))
	}
	const rows = []
	const walk = (node, dir, depth) => {
		for (const [name, child] of node.dirs) {
			rows.push({ type: "dir", name, path: `${dir}/${name}`, depth })
			walk(child, `${dir}/${name}`, depth + 1)
		}
		for (const name of node.files) rows.push({ type: "file", name, path: `${dir}/${name}`, depth })
	}
	walk(tree, searchRoot.value.replace(/\/+$/, ""), 0)
	return rows
})

const clampExplorerWidth = (w) => Math.min(400, Math.max(160, w))
const explorerWidth = ref(clampExplorerWidth(flow.state.prefs.explorerWidth ?? 220))

function startExplorerResize(event) {
	event.preventDefault()
	const handle = event.currentTarget
	handle.setPointerCapture(event.pointerId)
	const startX = event.clientX
	const startWidth = explorerWidth.value
	// the handle sits on the bar's left edge: dragging left widens it
	const move = (e) => (explorerWidth.value = clampExplorerWidth(startWidth - (e.clientX - startX)))
	const up = (e) => {
		handle.releasePointerCapture(e.pointerId)
		handle.removeEventListener("pointermove", move)
		handle.removeEventListener("pointerup", up)
		handle.removeEventListener("pointercancel", up)
		flow.setExplorerWidth(explorerWidth.value)
	}
	handle.addEventListener("pointermove", move)
	handle.addEventListener("pointerup", up)
	handle.addEventListener("pointercancel", up)
}

async function toggleExplorer() {
	explorerOpen.value = !explorerOpen.value
	if (!explorerOpen.value) return
	const data = await flow.listFiles() // refetch on every open: stays fresh
	if (data) {
		rootDir.value = data.path
		rootEntries.value = data.entries
	}
}

// the tree belongs to one session's cwd; a switch must not show the old one
watch(
	() => flow.state.sessionId,
	() => {
		explorerOpen.value = false
		rootDir.value = null
		rootEntries.value = null
		fileQuery.value = ""
	},
)

// Monaco objects stay out of Vue's reactivity: one editor, one model per tab.
// Models hold unsaved edits, so they live as long as their tab — the editor
// itself is recreated whenever the panel reopens. The library loads lazily on
// first open, so the chat page never pays for the editor bundle up front.
const editorEl = ref(null)
let monaco = null
let editor = null
const models = new Map()

// monaco infers the language from the file uri; only fill its gaps
const LANG_OVERRIDES = { vue: "html", svelte: "html" }

function modelFor(tab) {
	let model = models.get(tab.path)
	if (!model) {
		const ext = tab.name.split(".").pop()?.toLowerCase()
		model = monaco.editor.createModel(tab.content ?? "", LANG_OVERRIDES[ext], monaco.Uri.file(tab.path))
		// Dirty tracking via version ids: O(1) per keystroke (never a full-text
		// compare), and undoing back to the saved state reads as clean again.
		let savedVersion = model.getAlternativeVersionId()
		model.flowMarkSaved = (version = model.getAlternativeVersionId()) => (savedVersion = version)
		model.onDidChangeContent(() =>
			flow.markFileDirty(tab.path, model.getAlternativeVersionId() !== savedVersion),
		)
		models.set(tab.path, model)
	}
	return model
}

function syncModel() {
	const tab = activeTab.value
	if (!editor || !tab || tab.content == null) return
	const model = modelFor(tab)
	if (editor.getModel() !== model) editor.setModel(model)
}

watch(editorEl, async (el) => {
	if (el && !editor) {
		monaco ??= (await import("../monaco.js")).monaco
		if (!editorEl.value || editor) return // panel closed (or re-created) while loading
		editor = monaco.editor.create(editorEl.value, {
			automaticLayout: true,
			fontSize: 13.5,
			lineHeight: 23,
			padding: { top: 12, bottom: 12 },
			cursorBlinking: "smooth",
			minimap: { enabled: false },
			scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10 },
			overviewRulerLanes: 0,
			hideCursorInOverviewRuler: true,
			scrollBeyondLastLine: false,
			fixedOverflowWidgets: true,
		})
		applyTheme()
		editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, save)
		syncModel()
	} else if (!el && editor) {
		editor.dispose()
		editor = null
	}
})

watch([() => activeTab.value?.path, () => activeTab.value?.content != null], syncModel)

// a refetch (TurnFiles click, retry) refreshed the baseline; mirror it into a
// clean model — dirty models keep the user's edits
watch(
	() => activeTab.value?.content,
	(content) => {
		const tab = activeTab.value
		if (!tab || content == null) return
		const model = models.get(tab.path)
		if (model && !tab.dirty && model.getValue() !== content) {
			model.setValue(content)
			model.flowMarkSaved()
			flow.markFileDirty(tab.path, false)
		}
	},
)

// dispose models whose tab is gone (close, session switch)
watch(
	() => workspace.value.tabs.map((tab) => tab.path).join("\n"),
	() => {
		const alive = new Set(workspace.value.tabs.map((tab) => tab.path))
		for (const [path, model] of models) {
			if (alive.has(path)) continue
			if (editor?.getModel() === model) editor.setModel(null)
			model.dispose()
			models.delete(path)
		}
	},
)

// Editor theme derived from the app's frappe-ui tokens: the panel surface as
// background and the app's ink color for the cursor. Redefined on every toggle
// because the CSS variables change with [data-theme].
function cssColor(name) {
	const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
	if (raw.startsWith("#")) return raw
	const match = raw.match(/^rgba?\(([^)]+)\)/)
	if (!match) return null
	const [r, g, b] = match[1].split(/[\s,/]+/).map(Number)
	if ([r, g, b].some((v) => !Number.isFinite(v))) return null
	return "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")
}

function applyTheme() {
	if (!monaco) return
	const dark = flow.state.prefs.theme === "dark"
	const name = dark ? "flow-dark" : "flow-light"
	const colors = {
		"editor.background": cssColor("--surface-white"),
		"editorCursor.foreground": cssColor("--ink-gray-9"),
		"editor.lineHighlightBackground": cssColor("--surface-gray-1"),
		// opaque sliders: the default translucent band reads as a smear over code
		"scrollbarSlider.background": cssColor("--surface-gray-3"),
		"scrollbarSlider.hoverBackground": cssColor("--surface-gray-4"),
		"scrollbarSlider.activeBackground": cssColor("--surface-gray-4"),
	}
	monaco.editor.defineTheme(name, {
		base: dark ? "vs-dark" : "vs",
		inherit: true,
		rules: [],
		colors: Object.fromEntries(Object.entries(colors).filter(([, value]) => value)),
	})
	monaco.editor.setTheme(name)
}

watch(() => flow.state.prefs.theme, applyTheme)

onBeforeUnmount(() => {
	editor?.dispose()
	editor = null
	for (const model of models.values()) model.dispose()
	models.clear()
})

async function save() {
	const tab = activeTab.value
	const model = tab && models.get(tab.path)
	if (!tab || !model) return
	// snapshot version and text together; edits made while the save is in
	// flight stay marked dirty afterwards
	const version = model.getAlternativeVersionId()
	if (!(await flow.saveFile(tab.path, model.getValue()))) return
	model.flowMarkSaved(version)
	flow.markFileDirty(tab.path, model.getAlternativeVersionId() !== version)
}

function requestClose(tab) {
	if (!tab.dirty) return flow.closeFile(tab.path)
	dialog.confirm({
		title: "Discard changes?",
		message: `“${tab.name}” has unsaved changes.`,
		actions: [
			{ label: "Cancel", variant: "outline" },
			{ label: "Discard", variant: "solid", theme: "red", onClick: () => flow.closeFile(tab.path) },
		],
	})
}

const DEFAULT_WIDTH = 460
const clampWidth = (w) => Math.min(720, Math.max(320, w))
const width = ref(clampWidth(flow.state.prefs.workspaceWidth ?? DEFAULT_WIDTH))

function resetWidth() {
	width.value = DEFAULT_WIDTH
	flow.setWorkspaceWidth(DEFAULT_WIDTH)
}

function startResize(event) {
	event.preventDefault()
	const handle = event.currentTarget
	handle.setPointerCapture(event.pointerId)
	const startX = event.clientX
	const startWidth = width.value
	const move = (e) => (width.value = clampWidth(startWidth - (e.clientX - startX)))
	const up = (e) => {
		handle.releasePointerCapture(e.pointerId)
		handle.removeEventListener("pointermove", move)
		handle.removeEventListener("pointerup", up)
		handle.removeEventListener("pointercancel", up)
		flow.setWorkspaceWidth(width.value)
	}
	handle.addEventListener("pointermove", move)
	handle.addEventListener("pointerup", up)
	handle.addEventListener("pointercancel", up)
}
</script>

<style scoped>
.flow-backdrop-enter-active,
.flow-backdrop-leave-active {
	transition: opacity 0.2s ease;
}
.flow-backdrop-enter-from,
.flow-backdrop-leave-to {
	opacity: 0;
}

.flow-tab-strip {
	scrollbar-width: thin;
}

/* Breadcrumbs ships header-scale type; fit it to the path row */
.flow-crumbs :deep(button) {
	font-size: 13.5px;
	font-weight: 420;
	padding-top: 0;
	padding-bottom: 0;
	cursor: default;
}
.flow-crumbs :deep(span[aria-hidden="true"]) {
	font-size: 13.5px;
}

/* VSCode-style dirty marker: the dot swaps to an × when hovering the close button */
button:hover > .flow-dirty-dot {
	display: none;
}
button:hover > .flow-dirty-x {
	display: block;
}
</style>
