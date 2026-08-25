<template>
	<div class="overflow-hidden rounded-lg border border-outline-gray-1">
		<div class="flex h-9 items-center border-b border-outline-gray-1 bg-surface-gray-1 px-3 text-xs font-medium text-ink-gray-5">
			{{ files.length }} {{ files.length === 1 ? "file" : "files" }} changed
		</div>
		<div class="divide-y divide-outline-gray-1">
			<button
				v-for="file in files"
				:key="file.path"
				class="flex w-full items-center gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-surface-gray-1"
				:title="file.path"
				@click="flow.openFile(file.path)"
			>
				<FeatherIcon name="file" class="h-4 w-4 flex-none text-ink-gray-5" />
				<span class="flex-none text-sm font-medium text-ink-gray-9">{{ fileName(file.path) }}</span>
				<span class="min-w-0 truncate text-xs text-ink-gray-4">{{ dirPath(file.path) }}</span>
				<span class="flex-1" />
				<span class="flex-none font-mono text-xs text-ink-green-3">+{{ file.added }}</span>
				<span class="flex-none font-mono text-xs text-ink-red-3">-{{ file.removed }}</span>
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

import { compactDisplayText, fileName } from "../transcript.js"

defineProps({
	files: { type: Array, required: true }, // [{path, added, removed}]
})

const flow = inject("flow")
const cwd = computed(() => flow.state.session?.config?.cwd ?? null)

function dirPath(path) {
	const compact = compactDisplayText(path, cwd.value)
	const cut = compact.lastIndexOf("/")
	return cut > 0 ? compact.slice(0, cut) : ""
}
</script>
