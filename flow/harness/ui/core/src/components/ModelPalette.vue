<template>
	<PalettePanel title="Models" back :query="query" :busy="query !== debounced" @close="emit('close')" @back="emit('back')">
		<template #actions>
			<button
				class="grid h-6 w-6 place-items-center rounded-full text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
				title="Refresh models"
				@click="flow.refreshModels()"
			>
				<FeatherIcon
					name="refresh-cw"
					class="h-3.5 w-3.5"
					:class="flow.state.modelsLoading ? 'animate-spin' : ''"
				/>
			</button>
		</template>

		<div class="flow-palette-list min-h-0 flex-1 overflow-y-auto p-1">
			<button
				v-for="m in options"
				:key="m.name"
				data-palette-item
				:aria-current="m.name === currentModel ? 'true' : undefined"
				class="flow-palette-row"
				@click="choose(m.name)"
			>
				<span class="min-w-0 truncate">
					{{ m.custom ? `Use "${m.name}"` : shortName(m.name) }}
				</span>
				<!-- the current model is ticked by its name, so the provider keeps the right edge -->
				<FeatherIcon v-if="m.name === currentModel" name="check" class="h-4 w-4 flex-none" />
				<span class="flow-palette-hint ml-auto flex-none">{{ m.provider }}</span>
			</button>
			<LoadingState
				v-if="!options.length && flow.state.modelsLoading"
				class="justify-center px-3 py-8 text-xs text-ink-gray-5"
			/>
			<div v-else-if="!options.length" class="flex flex-col items-center gap-2 px-3 py-8 text-center">
				<span class="text-xs text-ink-gray-5">
					{{ providers ? "No models yet — connect a provider to get started." : "No models available." }}
				</span>
				<button
					v-if="providers"
					class="flex h-7 items-center gap-1.5 rounded-5 border border-outline-gray-2 px-2.5 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-1"
					@click="emit('providers')"
				>
					<FeatherIcon name="key" class="h-3.5 w-3.5" />
					Open providers
				</button>
			</div>
		</div>
	</PalettePanel>
</template>

<script setup>
import { computed, inject, toRef } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { useDebouncedValue } from "../debounce.js"
import LoadingState from "./LoadingState.vue"
import PalettePanel from "./PalettePanel.vue"

const props = defineProps({
	// hosts that manage providers elsewhere hide the setup link
	providers: { type: Boolean, default: true },
	query: { type: String, default: "" }, // the composer's text after its "/"
})
const emit = defineEmits(["close", "back", "providers"])
const flow = inject("flow")

const debounced = useDebouncedValue(toRef(props, "query"), 150)

const currentModel = computed(() => flow.state.conversation.model ?? flow.state.prefs.lastModel)

const options = computed(() => {
	const q = debounced.value.trim().toLowerCase()
	const rows = flow.state.models
		.filter((m) => !q || m.name.toLowerCase().includes(q))
		.map((m) => ({ name: m.name, provider: m.provider }))
	// a typed provider/model not in the list is usable as-is — discovery is a
	// suggestion, not a gate
	const typed = debounced.value.trim()
	if (typed.includes("/") && !rows.some((m) => m.name === typed)) {
		rows.push({ name: typed, provider: typed.split("/", 1)[0], custom: true })
	}
	return rows
})

function shortName(name) {
	return name.split("/").slice(1).join("/") || name
}

function choose(name) {
	flow.selectModel(name)
	emit("close")
}
</script>
