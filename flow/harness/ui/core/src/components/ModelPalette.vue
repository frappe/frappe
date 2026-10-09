<template>
	<PalettePanel title="Models" back @close="emit('close')" @back="emit('back')">
		<template #actions>
			<button
				class="flex h-7 w-7 items-center justify-center rounded-5 text-ink-gray-5 hover:bg-surface-gray-2"
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

		<template #search>
			<PaletteSearch v-model="query" placeholder="Search models" autofocus />
		</template>

		<div class="min-h-0 flex-1 overflow-y-auto p-1.5">
			<button
				v-for="m in options"
				:key="m.name"
				data-palette-item
				:aria-current="m.name === currentModel ? 'true' : undefined"
				class="flex w-full items-center gap-2.5 rounded-5 px-2.5 py-2 text-left hover:bg-surface-gray-2"
				@click="choose(m.name)"
			>
				<span
					class="flex h-7 w-7 flex-none items-center justify-center"
					:class="m.custom ? 'rounded-5 border border-dashed border-outline-gray-3' : ''"
				>
					<ProviderIcon :provider-id="m.provider" :size="22" />
				</span>
				<span class="min-w-0 flex-1">
					<span class="block truncate text-xs font-medium leading-4 text-ink-gray-9">
						{{ m.custom ? `Use "${m.name}"` : shortName(m.name) }}
					</span>
					<span class="mt-1 block truncate text-2xs leading-4 text-ink-gray-5">{{ m.provider }}</span>
				</span>
				<FeatherIcon
					v-if="m.name === currentModel"
					name="check"
					class="h-4 w-4 flex-none text-ink-gray-7"
				/>
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
import { computed, inject, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { useDebouncedValue } from "../debounce.js"
import LoadingState from "./LoadingState.vue"
import PalettePanel from "./PalettePanel.vue"
import PaletteSearch from "./PaletteSearch.vue"
import ProviderIcon from "./ProviderIcon.vue"

// hosts that manage providers elsewhere hide the setup link
defineProps({ providers: { type: Boolean, default: true } })
const emit = defineEmits(["close", "back", "providers"])
const flow = inject("flow")

const query = ref("")
const debounced = useDebouncedValue(query, 150)

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
