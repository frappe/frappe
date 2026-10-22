<template>
	<span class="relative min-w-0 max-w-[360px]">
		<!-- the row shrinks the wrapper; the button, sized to its text, must follow it. Its lists
		     hang from it -->
		<button
			ref="trigger"
			class="flex h-7 max-w-full items-center gap-1.5 rounded-5 px-2 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-2 dark:text-ink-gray-8"
			:class="pane ? 'bg-surface-gray-2' : ''"
			:title="`${currentModel ?? modelLabel} · thinking ${effortLabel}`"
			:aria-expanded="!!pane"
			@click="pane ? close() : (pane = 'root')"
		>
			<span class="min-w-0 truncate">{{ modelLabel }}</span>
			<template v-if="currentEffort !== 'default'">
				<span class="h-[3px] w-[3px] flex-none self-center rounded-full bg-surface-gray-4" />
				<span class="flex-none font-normal text-ink-gray-5 dark:text-ink-gray-6">{{ effortLabel }}</span>
			</template>
			<FeatherIcon
				name="chevron-down"
				class="h-3 w-3 flex-none text-ink-gray-4 transition-transform dark:text-ink-gray-6"
				:class="pane ? 'rotate-180' : ''"
			/>
		</button>
		<!-- its own lists, hung from it: a row each for the model and thinking, whose list takes their place -->
		<PalettePanel v-if="pane === 'root'" title="Model and thinking" dropdown @close="close">
			<div class="p-1">
				<button v-for="entry in entries" :key="entry.pane" data-palette-item class="flow-palette-row" @click="pane = entry.pane">
					<FeatherIcon :name="entry.icon" class="h-4 w-4 flex-none" />
					<span class="flex-none">{{ entry.label }}</span>
					<span class="flow-palette-hint min-w-0 flex-1 truncate">{{ entry.value }}</span>
					<FeatherIcon name="chevron-right" class="flow-palette-hint h-4 w-4 flex-none" />
				</button>
			</div>
		</PalettePanel>
		<ModelPalette v-else-if="pane === 'models'" dropdown :providers="providers" @close="close" @providers="openProviders" />
		<ThinkingPalette v-else-if="pane === 'thinking'" dropdown @close="close" />
	</span>
</template>

<script setup>
import { computed, inject, nextTick, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { EFFORT_LABELS, modelTitle } from "../transcript.js"
import ModelPalette from "./ModelPalette.vue"
import PalettePanel from "./PalettePanel.vue"
import ThinkingPalette from "./ThinkingPalette.vue"

// The composer's model button, with its own model and thinking lists; `open` asks the
// composer for its providers page, where an empty model list sends the user.
defineProps({ providers: { type: Boolean, default: false } })
const emit = defineEmits(["open"])
const flow = inject("flow")
const pane = ref(null) // null | "root" | "models" | "thinking"
const trigger = ref(null)

// a chat that is still loading shows its own model once known, never the last one picked
const currentModel = computed(
	() => flow.state.conversation.model ?? (flow.state.loading ? null : flow.state.prefs.lastModel),
)
// an open chat runs at its own level (none is the provider's default); a new chat at the last one picked
const currentEffort = computed(
	() => (flow.state.sessionId ? flow.state.conversation.reasoningEffort : flow.state.prefs.lastEffort) ?? "default",
)
const modelLabel = computed(() => {
	const model = currentModel.value
	if (!model) return flow.state.loading ? "" : "Choose Model"
	return modelTitle(model, flow.state.models)
})
const effortLabel = computed(() => EFFORT_LABELS[currentEffort.value] ?? "Default")
const entries = computed(() => [
	{ pane: "models", label: "Model", icon: "cpu", value: modelLabel.value },
	{ pane: "thinking", label: "Thinking", icon: "zap", value: effortLabel.value },
])

function close() {
	pane.value = null
	nextTick(() => trigger.value?.focus())
}

function openProviders() {
	pane.value = null
	emit("open", "providers")
}
</script>
