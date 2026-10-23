<template>
	<PalettePanel
		:title="title"
		:query="query"
		:busy="loading || query !== debouncedQuery"
		:full="rows === null"
		@close="emit('close')"
	>
		<div class="flow-palette-list overflow-y-auto p-1">
			<div class="-mt-1 flex h-8 items-center px-[11px] text-2xs font-medium text-ink-gray-5">
				<span class="truncate">{{ title }}</span>
			</div>
			<button
				v-if="!searchActive && dir"
				data-palette-item
				class="flow-palette-row"
				@click="goUp"
			>
				<FeatherIcon name="corner-left-up" class="h-4 w-4 flex-none" />
				<span class="flow-palette-hint min-w-0 flex-1 truncate">..</span>
			</button>
			<button
				v-for="row in rows"
				:key="row.path"
				data-palette-item
				class="flow-palette-row"
				@click="choose(row)"
			>
				<FeatherIcon :name="row.dir ? 'folder' : 'file-text'" class="h-4 w-4 flex-none" />
				<span class="min-w-0 flex-1 truncate">{{ row.label }}</span>
			</button>
			<LoadingState v-if="rows === null" class="justify-center px-3 py-8 text-xs text-ink-gray-5" />
			<div v-else-if="!rows.length" class="flow-palette-empty">
				{{ searchActive ? "No matching files" : "No files here" }}
			</div>
			<div v-if="truncated" class="px-3 pb-1 pt-2 text-center text-2xs text-ink-gray-5">
				More matches than shown — keep typing to narrow.
			</div>
		</div>
	</PalettePanel>
</template>

<script setup>
import { computed, inject, ref, toRef, watch } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { useDebouncedValue } from "../debounce.js"
import LoadingState from "./LoadingState.vue"
import PalettePanel from "./PalettePanel.vue"

const props = defineProps({ query: { type: String, default: "" } })
// "browse": a folder the search found is open in the list, so the query has to go
const emit = defineEmits(["pick", "browse", "close"])
const flow = inject("flow")

const dir = ref("") // cwd-relative directory being browsed while not searching
const rows = ref(null) // null until the first listing or search answers
const truncated = ref(false)
const loading = ref(true) // the rows answer an older query or folder

const debouncedQuery = useDebouncedValue(toRef(props, "query"), 150)
const searchActive = computed(() => debouncedQuery.value.trim() !== "")
const title = computed(() => (searchActive.value ? "Files" : dir.value || "Files"))

function goUp() {
	dir.value = dir.value.split("/").slice(0, -1).join("/")
}

function choose(row) {
	if (!row.dir) return emit("pick", row.path)
	dir.value = row.path
	if (searchActive.value) emit("browse")
}

// Browse the cwd a level at a time, and switch to the explorer's recursive
// name search as soon as something is typed after the "@".
async function load() {
	const query = debouncedQuery.value.trim()
	const at = dir.value
	const cwd = flow.explorerCwd()
	loading.value = true
	// the previous rows stay rendered while the request is in flight — blanking
	// the list between keystrokes is what makes it flicker
	const data = query ? await flow.searchFiles(query) : await flow.listFiles(at)
	// stale response: the query, the browsed directory, or the cwd moved on
	if (debouncedQuery.value.trim() !== query || dir.value !== at || flow.explorerCwd() !== cwd) return
	rows.value = query
		? (data?.matches ?? []).map((match) => {
				const path = match.replace(/\/$/, "") // a folder's ends in a slash
				return { path, label: path, dir: path !== match }
			})
		: (data?.entries ?? []).map((entry) => ({
				path: at ? `${at}/${entry.name}` : entry.name,
				label: entry.name,
				dir: entry.type === "dir",
			}))
	truncated.value = !!query && !!data?.truncated
	loading.value = false
}

watch([debouncedQuery, dir, () => flow.explorerCwd()], load, { immediate: true })
</script>
