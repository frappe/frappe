<template>
	<div
		v-show="open"
		class="relative flex flex-none flex-col border-l border-outline-gray-1"
		:style="{ width: width + 'px' }"
	>
		<div
			v-if="mode === 'diff'"
			class="flex h-9 flex-none items-center border-b border-outline-gray-1 px-3 text-xs font-medium text-ink-gray-5"
		>
			{{ changedFiles.length }} {{ changedFiles.length === 1 ? "file" : "files" }} changed
		</div>
		<div v-if="mode === 'files'" class="flex-none px-1.5 pt-1.5">
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
			<!-- diff mode: only the files this session edited or wrote -->
			<template v-if="mode === 'diff'">
				<div
					v-for="file in changedFiles"
					:key="file.path"
					role="button"
					tabindex="0"
					class="flex cursor-pointer items-center gap-1.5 rounded py-[5px] pl-2 pr-1.5 text-sm hover:bg-surface-gray-2"
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
					<span class="flex-none font-mono text-2xs text-ink-green-3">+{{ file.added }}</span>
					<span class="flex-none font-mono text-2xs text-ink-red-3">-{{ file.removed }}</span>
				</div>
				<div v-if="!changedFiles.length" class="px-1.5 py-2 text-2xs text-ink-gray-4">
					No files changed in this session
				</div>
			</template>
			<!-- searching: a pruned tree of matches only, all branches open -->
			<template v-else-if="searchActive">
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
			@pointerdown="startResize"
		/>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

import { useDebouncedValue } from "../debounce.js"
import { aggregateFileChanges, fileName } from "../transcript.js"
import FileTree from "./FileTree.vue"

const props = defineProps({
	open: { type: Boolean, default: false },
	// "files": cwd tree with search; "diff": the session's changed files
	mode: { type: String, required: true },
})

const flow = inject("flow")
const activeTab = computed(
	() => flow.state.workspace.tabs.find((tab) => tab.path === flow.state.workspace.active) ?? null,
)
const changedFiles = computed(() => aggregateFileChanges(flow.state.conversation.entries))

const rootDir = ref(null)
const rootEntries = ref(null)

async function loadRoot() {
	const cwd = flow.explorerCwd()
	const data = await flow.listFiles() // refetch on every open: stays fresh
	if (!data || flow.explorerCwd() !== cwd) return // a cwd switch mid-flight: not our tree
	rootDir.value = data.path
	rootEntries.value = data.entries
}

watch(
	() => [props.open, props.mode],
	([open, mode]) => {
		if (open && mode === "files") void loadRoot()
	},
	{ immediate: true },
)

// the tree belongs to the browsed cwd; a switch must not show the old one
watch(
	() => flow.explorerCwd(),
	() => {
		rootDir.value = null
		rootEntries.value = null
		fileQuery.value = ""
		if (props.open && props.mode === "files") void loadRoot()
	},
)

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
	const cwd = flow.explorerCwd()
	const data = await flow.searchFiles(query)
	// stale response: the query or the browsed cwd moved on
	if (debouncedFileQuery.value.trim() !== query || flow.explorerCwd() !== cwd) return
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

const clampWidth = (w) => Math.min(400, Math.max(160, w))
const width = ref(clampWidth(flow.state.prefs.explorerWidth ?? 220))

function startResize(event) {
	event.preventDefault()
	const handle = event.currentTarget
	handle.setPointerCapture(event.pointerId)
	const startX = event.clientX
	const startWidth = width.value
	// the handle sits on the bar's left edge: dragging left widens it
	const move = (e) => (width.value = clampWidth(startWidth - (e.clientX - startX)))
	const up = (e) => {
		handle.releasePointerCapture(e.pointerId)
		handle.removeEventListener("pointermove", move)
		handle.removeEventListener("pointerup", up)
		handle.removeEventListener("pointercancel", up)
		flow.setExplorerWidth(width.value)
	}
	handle.addEventListener("pointermove", move)
	handle.addEventListener("pointerup", up)
	handle.addEventListener("pointercancel", up)
}
</script>
