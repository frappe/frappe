<template>
	<div class="overflow-hidden rounded-6 border border-outline-gray-1">
		<div class="flex h-9 items-center border-b border-outline-gray-1 bg-surface-gray-1 px-3 text-xs font-medium text-ink-gray-5">
			{{ files.length }} {{ files.length === 1 ? "file" : "files" }} changed
		</div>
		<div class="divide-y divide-outline-gray-1">
			<button
				v-for="file in shown"
				:key="file.path"
				class="flex w-full items-center gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-surface-gray-1"
				:title="file.path"
				@click="flow.openDiffFile(file.path)"
			>
				<FeatherIcon name="file" class="h-4 w-4 flex-none text-ink-gray-5" />
				<span class="flex-none text-sm font-medium text-ink-gray-9">{{ fileName(file.path) }}</span>
				<span class="min-w-0 truncate text-xs text-ink-gray-4">{{ dirPath(file.path) }}</span>
				<span class="flex-1" />
				<span class="flex-none font-mono text-xs text-ink-green-5 dark:text-ink-green-7">+{{ file.added }}</span>
				<span class="flex-none font-mono text-xs text-ink-red-6">-{{ file.removed }}</span>
			</button>
			<button
				v-if="files.length > VISIBLE"
				class="w-full py-2 text-center text-xs text-ink-gray-5 transition-colors hover:bg-surface-gray-1 hover:text-ink-gray-8"
				@click="expanded = !expanded"
			>
				{{ expanded ? "Show less" : `Show all ${files.length} files` }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { compactDisplayText, fileName } from "../transcript.js"

const props = defineProps({
	files: { type: Array, required: true }, // [{path, added, removed}]
})

const VISIBLE = 4
const expanded = ref(false)
const shown = computed(() => (expanded.value ? props.files : props.files.slice(0, VISIBLE)))

const flow = inject("flow")
const cwd = computed(() => flow.state.session?.config?.cwd ?? null)

function dirPath(path) {
	const compact = compactDisplayText(path, cwd.value)
	const cut = compact.lastIndexOf("/")
	return cut > 0 ? compact.slice(0, cut) : ""
}
</script>
