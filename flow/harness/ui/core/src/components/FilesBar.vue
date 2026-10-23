<template>
	<!-- the bar animates its width open/closed; the fixed-width inner column rides
	     the leading edge (border included), so content slides in instead of squishing -->
	<div
		class="relative flex flex-none overflow-hidden"
		:class="resizing ? '' : 'transition-[width] duration-200 ease-in-out'"
		:style="{ width: (open ? width : 0) + 'px' }"
	>
		<div
			class="flex min-h-0 flex-1 flex-col border-l border-outline-gray-1"
			:style="{ width: width + 'px' }"
		>
			<div
				v-if="mode === 'diff'"
				class="flex h-9 flex-none items-center border-b border-outline-gray-1 px-3 text-xs font-medium text-ink-gray-5"
			>
				{{ gitFiles.length }} {{ gitFiles.length === 1 ? "file" : "files" }} changed
			</div>
			<div v-if="mode === 'files'" class="flex-none px-1.5 pt-1.5">
				<div
					class="flex h-8 items-center gap-2 rounded-5 border border-outline-gray-2 bg-surface-base px-2 text-ink-gray-5 transition-colors focus-within:border-outline-gray-3"
				>
					<FeatherIcon name="search" class="h-3.5 w-3.5 flex-none" />
					<input
						ref="searchInput"
						v-model="fileQuery"
						placeholder="Search files"
						spellcheck="false"
						class="h-full w-full min-w-0 border-0 bg-transparent p-0 text-xs text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
					/>
					<button
						v-if="fileQuery"
						class="grid h-4 w-4 flex-none place-items-center rounded-4 text-ink-gray-4 hover:text-ink-gray-8"
						title="Clear"
						@click="fileQuery = ''"
					>
						<FeatherIcon name="x" class="h-3 w-3" />
					</button>
				</div>
			</div>
			<div class="min-h-0 flex-1 overflow-y-auto px-1.5 py-1.5">
				<!-- diff mode: the project's uncommitted changes -->
				<template v-if="mode === 'diff'">
					<div
						v-for="file in gitFiles"
						:key="file.path"
						role="button"
						tabindex="0"
						class="flex cursor-pointer items-center gap-1.5 rounded-4 py-[5px] pl-2 pr-1.5 text-sm hover:bg-surface-gray-2"
						:class="
							activeTab?.path === file.path
								? 'bg-surface-gray-3 font-medium text-ink-gray-9'
								: 'text-ink-gray-8'
						"
						:title="file.path"
						@click="flow.openDiffFile(file.path)"
						@keydown.enter.prevent="flow.openDiffFile(file.path)"
					>
						<span class="grid h-4 w-4 flex-none place-items-center">
							<FeatherIcon name="file" class="h-3.5 w-3.5 text-ink-gray-5" />
						</span>
						<span class="min-w-0 truncate">{{ fileName(file.path) }}</span>
						<span class="flex-1" />
						<span class="flex-none font-mono text-2xs text-ink-green-5 dark:text-ink-green-7">+{{ file.added }}</span>
						<span class="flex-none font-mono text-2xs text-ink-red-6">-{{ file.removed }}</span>
					</div>
					<div v-if="changes && !changes.root" class="px-1.5 py-2 text-2xs text-ink-gray-4">
						Not a git repository
					</div>
					<div v-else-if="changes && !gitFiles.length" class="px-1.5 py-2 text-2xs text-ink-gray-4">
						No uncommitted changes
					</div>
					<LoadingState v-else-if="changesPending" class="px-1.5 py-2 text-2xs text-ink-gray-4" />
				</template>
				<!-- searching: a pruned tree of matches only, branches open until folded -->
				<template v-else-if="searchActive">
					<LoadingState v-if="searchMatches === null" class="px-1.5 py-2 text-2xs text-ink-gray-4">
						Searching…
					</LoadingState>
					<template v-else>
						<template v-for="row in searchRows" :key="row.path">
							<!-- a folder found by its name opens onto all it holds, not just what else was found -->
							<FileTree
								v-if="row.type === 'found'"
								:entry="{ name: row.name, type: 'dir' }"
								:dir="row.dir"
								:depth="row.depth"
							/>
							<div
								v-else
								role="button"
								tabindex="0"
								:aria-expanded="row.type === 'dir' ? row.open : undefined"
								class="relative flex cursor-pointer items-center gap-1.5 rounded-4 py-[5px] pr-1.5 text-sm text-ink-gray-8 hover:bg-surface-gray-2"
								:style="{ paddingLeft: row.depth * 16 + 8 + 'px' }"
								:title="row.path"
								@click="activateRow(row)"
								@keydown.enter.prevent="activateRow(row)"
								@keydown.space.prevent="activateRow(row)"
							>
								<span
									v-for="level in row.depth"
									:key="level"
									class="pointer-events-none absolute inset-y-0 w-px bg-[--outline-gray-1]"
									:style="{ left: (level - 1) * 16 + 16 + 'px' }"
								/>
								<span class="grid h-4 w-4 flex-none place-items-center">
									<FeatherIcon
										:name="row.type === 'dir' ? (row.open ? 'chevron-down' : 'chevron-right') : 'file'"
										class="h-3.5 w-3.5 text-ink-gray-5"
									/>
								</span>
								<span class="min-w-0 truncate">{{ row.name }}</span>
							</div>
						</template>
						<div v-if="!searchRows.length" class="px-1.5 py-2 text-2xs text-ink-gray-4">
							No matches
						</div>
						<div v-else-if="searchTruncated" class="px-1.5 py-2 text-2xs text-ink-gray-4">
							More matches not shown — narrow the search
						</div>
					</template>
				</template>
				<!-- hidden, not unmounted, while searching: opened folders survive a search -->
				<div v-if="mode === 'files' && rootDir" v-show="!searchActive">
					<FileTree v-for="entry in rootEntries" :key="entry.name" :entry="entry" :dir="rootDir" />
					<div v-if="!rootEntries.length" class="px-1.5 py-2 text-2xs text-ink-gray-4">
						Empty folder
					</div>
				</div>
				<LoadingState
					v-else-if="mode === 'files' && rootLoading && !searchActive"
					class="px-1.5 py-2 text-2xs text-ink-gray-4"
				/>
			</div>
		</div>
		<div
			class="absolute inset-y-0 left-0 z-10 w-1 cursor-col-resize hover:bg-[--outline-gray-2] active:bg-[--outline-gray-3]"
			title="Drag to resize"
			@pointerdown="startResize"
		/>
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, reactive, ref, watch } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { useDebouncedValue } from "../debounce.js"
import { fileName } from "../transcript.js"
import FileTree from "./FileTree.vue"
import LoadingState from "./LoadingState.vue"

const props = defineProps({
	open: { type: Boolean, default: false },
	// "files": cwd tree with search; "diff": the project's uncommitted changes
	mode: { type: String, required: true },
})

const flow = inject("flow")
const activeTab = computed(
	() => flow.state.workspace.tabs.find((tab) => tab.path === flow.state.workspace.active) ?? null,
)

const rootDir = ref(null)
const rootEntries = ref(null)
const rootLoading = ref(false)

async function loadRoot() {
	const cwd = flow.explorerCwd()
	rootLoading.value = true
	const data = await flow.listFiles() // refetch on every open: stays fresh
	if (flow.explorerCwd() !== cwd) return // a cwd switch mid-flight: not our tree
	rootLoading.value = false
	if (!data) return
	rootDir.value = data.path
	rootEntries.value = data.entries
}

// The diff list polls while visible, so edits from the agent, the editor, or
// outside Flow all show up. Chained (not an interval): a slow response never
// overlaps the next one. Bumping pollId retires the loop and its stale replies.
const DIFF_POLL_MS = 3000
const changes = ref(null) // {root, files}; root is null outside a git repo
const changesPending = ref(false) // the list's first answer is on its way
const gitFiles = computed(() => changes.value?.files ?? [])
let pollId = 0

async function pollChanges(id) {
	changesPending.value = !changes.value
	while (id === pollId) {
		const data = await flow.gitChanges()
		if (id !== pollId) return
		changesPending.value = false
		if (data) changes.value = data
		await new Promise((resolve) => setTimeout(resolve, DIFF_POLL_MS))
	}
}

watch(
	() => [props.open, props.mode],
	([open, mode]) => {
		pollId++
		if (!open) return
		if (mode === "files") void loadRoot()
		if (mode === "diff") void pollChanges(pollId)
	},
	{ immediate: true },
)

onBeforeUnmount(() => pollId++)

// the tree and diff list belong to the browsed cwd; a switch must not show the old ones
watch(
	() => flow.explorerCwd(),
	() => {
		rootDir.value = null
		rootEntries.value = null
		fileQuery.value = ""
		changes.value = null
		pollId++
		if (!props.open) return
		if (props.mode === "files") void loadRoot()
		if (props.mode === "diff") void pollChanges(pollId)
	},
)

// Search runs server-side (recursive, pruned to matches); the result renders
// as an opened tree of only the branches that contain matches. Clearing
// the query falls back to the normal lazy tree with its manual expansion.
const fileQuery = ref("")
const searchInput = ref(null)
// the Files view opened by hand puts the caret in its search, a restored one leaves it be.
// Two timeouts: a menu it was opened from hands the focus back to its trigger in one, set as it closes
watch(
	() => props.open && props.mode === "files" && flow.state.workspace.focusSearch,
	(asked) => {
		if (!asked) return
		flow.state.workspace.focusSearch = false
		setTimeout(() => setTimeout(() => searchInput.value?.focus({ preventScroll: true })))
	},
	{ immediate: true },
)
const debouncedFileQuery = useDebouncedValue(fileQuery, 200)
const searchActive = computed(() => debouncedFileQuery.value.trim() !== "")
const searchRoot = ref(null)
const searchMatches = ref(null) // null while a search is in flight
const searchTruncated = ref(false)
// folders folded in the results: kept while the query is refined, dropped once the box is emptied
const collapsedDirs = reactive(new Set())
// the raw box, not the debounced query, which a quick retype skips past; applied with the next results
let dropFolds = false
watch(fileQuery, (raw) => {
	if (!raw.trim()) dropFolds = true
})

watch(debouncedFileQuery, async (raw) => {
	const query = raw.trim()
	if (!query) {
		searchMatches.value = null // reset, so the next search shows its own state
		return
	}
	// Previous results stay rendered while the new search is in flight —
	// blanking between keystrokes is what makes the list flicker. Stable row
	// keys (paths) then let Vue patch only the rows that actually changed.
	const cwd = flow.explorerCwd()
	const data = await flow.searchFiles(query)
	// stale response: the query or the browsed cwd moved on
	if (debouncedFileQuery.value.trim() !== query || flow.explorerCwd() !== cwd) return
	if (dropFolds) collapsedDirs.clear()
	dropFolds = false
	searchRoot.value = data?.path ?? null
	searchMatches.value = data?.matches ?? []
	searchTruncated.value = data?.truncated ?? false
})

const searchRows = computed(() => {
	if (!searchMatches.value?.length || !searchRoot.value) return []
	const tree = { dirs: new Map(), files: [] }
	for (const rel of searchMatches.value) {
		const folder = rel.endsWith("/") // a folder's ends in a slash
		const parts = rel.replace(/\/$/, "").split("/")
		let node = tree
		for (const part of folder ? parts : parts.slice(0, -1)) {
			if (!node.dirs.has(part)) node.dirs.set(part, { dirs: new Map(), files: [] })
			node = node.dirs.get(part)
		}
		if (folder) node.found = true
		else node.files.push(parts.at(-1))
	}
	const rows = []
	const walk = (node, dir, depth) => {
		for (const [name, child] of node.dirs) {
			const path = `${dir}/${name}`
			if (child.found) {
				rows.push({ type: "found", name, path, dir, depth })
				continue
			}
			const open = !collapsedDirs.has(path)
			rows.push({ type: "dir", name, path, depth, open })
			if (open) walk(child, path, depth + 1)
		}
		for (const name of node.files) rows.push({ type: "file", name, path: `${dir}/${name}`, depth })
	}
	walk(tree, searchRoot.value.replace(/\/+$/, ""), 0)
	return rows
})

function activateRow(row) {
	if (row.type === "file") return flow.openFile(row.path)
	if (collapsedDirs.has(row.path)) collapsedDirs.delete(row.path)
	else collapsedDirs.add(row.path)
}

const clampWidth = (w) => Math.min(400, Math.max(160, w))
const width = ref(clampWidth(flow.state.prefs.explorerWidth ?? 220))
const resizing = ref(false) // a drag must track the pointer, not the width transition

function startResize(event) {
	event.preventDefault()
	const handle = event.currentTarget
	handle.setPointerCapture(event.pointerId)
	resizing.value = true
	const startX = event.clientX
	const startWidth = width.value
	// the handle sits on the bar's left edge: dragging left widens it
	const move = (e) => (width.value = clampWidth(startWidth - (e.clientX - startX)))
	const up = (e) => {
		handle.releasePointerCapture(e.pointerId)
		handle.removeEventListener("pointermove", move)
		handle.removeEventListener("pointerup", up)
		handle.removeEventListener("pointercancel", up)
		resizing.value = false
		flow.setExplorerWidth(width.value)
	}
	handle.addEventListener("pointermove", move)
	handle.addEventListener("pointerup", up)
	handle.addEventListener("pointercancel", up)
}
</script>
