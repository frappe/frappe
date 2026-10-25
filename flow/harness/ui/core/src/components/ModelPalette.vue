<template>
	<PalettePanel
		title="Models"
		:back="!dropdown"
		:dropdown="dropdown"
		:query="search"
		:busy="search !== debounced"
		@close="emit('close')"
		@back="emit('back')"
	>
		<template v-if="!dropdown" #actions>
			<button
				class="grid h-6 w-6 place-items-center rounded-full text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
				title="Refresh models"
				@click="flow.refreshModels()"
			>
				<FeatherIcon name="refresh-cw" class="h-3.5 w-3.5" :class="flow.state.modelsLoading ? 'animate-spin' : ''" />
			</button>
		</template>

		<!-- hung from the model button, the list searches with a field of its own -->
		<div v-if="dropdown" class="flex flex-none items-center gap-1 pl-1 pr-2.5 pt-1">
			<input
				ref="field"
				v-model="typed"
				placeholder="Search models…"
				class="h-8 min-w-0 flex-1 border-0 bg-transparent px-[11px] text-sm text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
			/>
			<button
				class="grid h-6 w-6 flex-none place-items-center rounded-full text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
				title="Refresh models"
				@click="flow.refreshModels()"
			>
				<FeatherIcon name="refresh-cw" class="h-3.5 w-3.5" :class="flow.state.modelsLoading ? 'animate-spin' : ''" />
			</button>
		</div>

		<div class="flow-palette-list min-h-0 flex-1 overflow-y-auto p-1">
			<template v-for="(group, i) in groups" :key="group.provider">
				<!-- a heading takes a row's height; the first sits in the list's top padding -->
				<div class="flex h-8 items-center px-[11px] text-2xs font-medium text-ink-gray-5" :class="i ? 'mt-2' : '-mt-1'">
					{{ group.provider }}
				</div>
				<button
					v-for="m in group.models"
					:key="m.name"
					data-palette-item
					:aria-current="m.name === currentModel ? 'true' : undefined"
					class="flow-palette-row"
					:title="m.name"
					@click="choose(m.name)"
				>
					<span class="min-w-0 truncate">{{ m.title }}</span>
					<FeatherIcon v-if="m.name === currentModel" name="check" class="ml-auto h-4 w-4 flex-none" />
				</button>
			</template>
			<!-- a typed provider/model not in the list is usable as-is: discovery is a suggestion, not a gate -->
			<button v-if="custom" data-palette-item class="flow-palette-row" @click="choose(custom)">
				<span class="min-w-0 truncate">Use "{{ custom }}"</span>
			</button>
			<LoadingState
				v-if="!groups.length && !custom && flow.state.modelsLoading"
				class="justify-center px-3 py-8 text-xs text-ink-gray-5"
			/>
			<div v-else-if="!groups.length && !custom && flow.state.models.length" class="flow-palette-empty">
				No matching models
			</div>
			<!-- none at all: a line saying so, and the way to connect a provider as a row -->
			<template v-else-if="!groups.length && !custom">
				<div class="flow-palette-empty">{{ providers ? "No models yet" : "No models available" }}</div>
				<button v-if="providers" data-palette-item class="flow-palette-row" @click="emit('providers')">
					<FeatherIcon name="key" class="h-4 w-4 flex-none" />
					Connect a provider
				</button>
			</template>
		</div>
	</PalettePanel>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { useDebouncedValue } from "../debounce.js"
import { layout } from "../layout.js"
import { modelTitle } from "../transcript.js"
import LoadingState from "./LoadingState.vue"
import PalettePanel from "./PalettePanel.vue"

const props = defineProps({
	// hosts that manage providers elsewhere hide the setup link
	providers: { type: Boolean, default: true },
	query: { type: String, default: "" }, // the composer's text after its "/"
	// hung from the model button with its own search, not over the composer
	dropdown: { type: Boolean, default: false },
})
const emit = defineEmits(["close", "back", "providers"])
const flow = inject("flow")

const typed = ref("")
const field = ref(null)
const search = computed(() => (props.dropdown ? typed.value : props.query))
const debounced = useDebouncedValue(search, 150)
// a phone's list leaves its search for a tap, rather than raise the keyboard over it
onMounted(() => layout.phone || field.value?.focus())

const currentModel = computed(() => flow.state.conversation.model ?? flow.state.prefs.lastModel)

// each provider's models under its name, matched by every word of the search in their name or id
const groups = computed(() => {
	const words = debounced.value.trim().toLowerCase().split(/\s+/).filter(Boolean)
	const groups = new Map()
	for (const m of flow.state.models) {
		const title = m.display_name || modelTitle(m.name)
		const text = `${title} ${m.name}`.toLowerCase()
		if (!words.every((word) => text.includes(word))) continue
		if (!groups.has(m.provider)) groups.set(m.provider, [])
		groups.get(m.provider).push({ name: m.name, title })
	}
	return [...groups].map(([provider, models]) => ({ provider, models }))
})
const custom = computed(() => {
	const name = debounced.value.trim()
	return name.includes("/") && !flow.state.models.some((m) => m.name === name) ? name : null
})

function choose(name) {
	flow.selectModel(name)
	emit("close")
}
</script>
