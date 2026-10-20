<template>
	<span class="relative min-w-0">
		<!-- its list hangs from it -->
		<button
			ref="trigger"
			class="flex max-w-full items-center gap-1.5 rounded-4 px-1.5 py-1 hover:bg-surface-gray-2 hover:text-ink-gray-8"
			:class="open ? 'bg-surface-gray-2' : ''"
			title="Agent preset"
			:aria-expanded="open"
			:disabled="disabled"
			@click="open ? close() : show()"
		>
			<FeatherIcon name="layers" class="h-3.5 w-3.5 flex-none" />
			<span class="truncate">{{ flow.activePreset()?.name ?? "Standard" }}</span>
			<FeatherIcon
				name="chevron-down"
				class="h-3 w-3 flex-none text-ink-gray-4 transition-transform dark:text-ink-gray-6"
				:class="open ? 'rotate-180' : ''"
			/>
		</button>
		<PalettePanel v-if="open" title="Agent preset" dropdown align="left" :width="264" :query="search" @close="close">
			<div class="flex flex-none pl-1 pr-2.5 pt-1">
				<input
					ref="field"
					v-model="search"
					placeholder="Search presets…"
					class="h-8 min-w-0 flex-1 border-0 bg-transparent px-[11px] text-sm text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
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
					<FeatherIcon v-if="row.id === current" name="check" class="ml-auto h-4 w-4 flex-none" />
				</button>
				<div v-if="!rows.length" class="flow-palette-empty">No matching presets</div>
				<!-- a search that finds none: the way to a new one -->
				<button v-if="!rows.length" data-palette-item class="flow-palette-row" @click="create">
					<FeatherIcon name="plus" class="h-4 w-4 flex-none" />
					Create a preset
				</button>
			</div>
		</PalettePanel>
	</span>
</template>

<script setup>
import { computed, inject, nextTick, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

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
