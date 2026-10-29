<template>
	<span class="relative min-w-0">
		<!-- its list hangs from it -->
		<button
			ref="trigger"
			class="flex h-7 max-w-full items-center gap-1.5 rounded-5 px-2 hover:bg-surface-gray-3 hover:text-ink-gray-8 dark:hover:bg-surface-gray-2"
			:class="open ? 'bg-surface-gray-3 dark:bg-surface-gray-2' : ''"
			title="Agent preset"
			:aria-expanded="open"
			:disabled="disabled"
			@click="open ? close() : show()"
		>
			<span class="lucide-layers size-3.5 flex-none" aria-hidden="true" />
			<span class="truncate">{{ flow.activePreset()?.name ?? "Standard" }}</span>
			<span
				class="lucide-chevron-down size-3 flex-none text-ink-gray-4 transition-transform dark:text-ink-gray-6"
				:class="open ? 'rotate-180' : ''"
				aria-hidden="true"
			/>
		</button>
		<PalettePanel v-if="open" title="Agent preset" dropdown align="left" :width="264" :query="search" @close="close">
			<div class="flex flex-none pl-1 pr-2.5 pt-1">
				<input
					ref="field"
					v-model="search"
					placeholder="Search presets…"
					class="h-8 min-w-0 flex-1 border-0 bg-transparent px-[11px] text-base text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
				/>
			</div>
			<div class="flow-palette-list min-h-0 flex-1 overflow-y-auto p-1">
				<button
					v-for="row in rows"
					:key="row.id ?? ''"
					data-palette-item
					:aria-current="row.id === current ? 'true' : undefined"
					class="flow-palette-row"
					@click="choose(row.id)"
				>
					<span class="min-w-0 truncate">{{ row.name }}</span>
					<span
						v-if="row.id === current"
						class="lucide-check ml-auto size-4 flex-none"
						aria-hidden="true"
					/>
				</button>
				<div v-if="!rows.length" class="flow-palette-empty">No matching presets</div>
				<!-- a search that finds none: the way to a new one -->
				<button v-if="!rows.length" data-palette-item class="flow-palette-row" @click="create">
					<span class="lucide-plus size-4 flex-none" aria-hidden="true" />
					Create a preset
				</button>
			</div>
		</PalettePanel>
	</span>
</template>

<script setup>
import { computed, inject, nextTick, ref } from "vue"

import { layout } from "../layout.js"
import PalettePanel from "./PalettePanel.vue"

// A new chat's agent preset: Standard (core tools, the built-in prompt) or one saved in settings
defineProps({ disabled: { type: Boolean, default: false } })
const flow = inject("flow")
const open = ref(false)
const search = ref("")
const trigger = ref(null)
const field = ref(null)

const current = computed(() => flow.activePreset()?.id ?? null)
// matched by every word of the search in their name
const rows = computed(() => {
	const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean)
	return [{ id: null, name: "Standard" }, ...flow.state.presets].filter((row) =>
		words.every((word) => row.name.toLowerCase().includes(word)),
	)
})

// a phone's list leaves its search for a tap, rather than raise the keyboard over it
function show() {
	search.value = ""
	open.value = true
	nextTick(() => layout.phone || field.value?.focus())
}

function close() {
	open.value = false
	nextTick(() => trigger.value?.focus())
}

function choose(id) {
	flow.setActivePreset(id)
	close()
}

// the settings dialog takes the focus
function create() {
	open.value = false
	flow.createPreset()
}
</script>
