<template>
	<PalettePanel :title="title" :autofocus="false" :busy="loading || query !== debouncedQuery" @close="emit('close')">
		<div class="overflow-y-auto p-1.5">
			<button
				v-if="!searchActive && dir"
				data-palette-item
				class="flex w-full items-center gap-2.5 rounded-5 px-2.5 py-2 text-left hover:bg-surface-gray-2"
				@click="goUp"
			>
				<span
					class="flex h-7 w-7 flex-none items-center justify-center rounded-5 border border-outline-gray-1 bg-surface-gray-1 text-ink-gray-6"
				>
					<FeatherIcon name="corner-left-up" class="h-3.5 w-3.5" />
				</span>
				<span class="min-w-0 flex-1 truncate text-xs font-medium leading-4 text-ink-gray-5">..</span>
			</button>
			<button
				v-for="row in rows"
				:key="row.path"
				data-palette-item
				class="flex w-full items-center gap-2.5 rounded-5 px-2.5 py-2 text-left hover:bg-surface-gray-2"
				@click="choose(row)"
			>
				<span
					class="flex h-7 w-7 flex-none items-center justify-center rounded-5 border border-outline-gray-1 bg-surface-gray-1 text-ink-gray-6"
				>
					<FeatherIcon :name="row.dir ? 'folder' : 'file-text'" class="h-3.5 w-3.5" />
				</span>
				<span class="min-w-0 flex-1 truncate text-xs font-medium leading-4 text-ink-gray-9">{{ row.label }}</span>
			</button>
			<LoadingState v-if="rows === null" class="justify-center px-3 py-8 text-xs text-ink-gray-5" />
			<div v-else-if="!rows.length" class="px-3 py-8 text-center text-xs text-ink-gray-5">
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
const emit = defineEmits(["pick", "close"])
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
	if (row.dir) dir.value = row.path
	else emit("pick", row.path)
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
		? (data?.matches ?? []).map((path) => ({ path, label: path, dir: false }))
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
