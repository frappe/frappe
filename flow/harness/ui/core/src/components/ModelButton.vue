<template>
	<span class="relative min-w-0 max-w-[360px]">
		<!-- the row shrinks the wrapper; the button, sized to its text, must follow it. Its lists
		     hang from it -->
		<button
			ref="trigger"
			class="flex h-7 max-w-full items-center gap-1.5 rounded-5 px-2 text-base text-ink-gray-7 hover:bg-surface-gray-2 dark:text-ink-gray-8"
			:class="pane ? 'bg-surface-gray-2' : ''"
			:title="`${currentModel ?? modelLabel} · thinking ${effortLabel}`"
			:aria-expanded="!!pane"
			@click="pane ? close() : open()"
		>
			<span class="min-w-0 truncate">{{ modelLabel }}</span>
			<template v-if="currentEffort !== 'default'">
				<span class="h-[3px] w-[3px] flex-none self-center rounded-full bg-surface-gray-4" />
				<span class="flex-none text-ink-gray-5 dark:text-ink-gray-6">{{ effortLabel }}</span>
			</template>
		</button>
		<!-- its own menu, hung from it: a row each for the model and thinking, whose list opens beside
		     it on hover (in its place in a narrow frame, the Desk panel's or a phone's) -->
		<PalettePanel
			v-if="pane && !(sub && layout.narrow)"
			title="Model and thinking"
			dropdown
			:width="ROOT_WIDTH"
			:passive="!!sub"
			@close="close"
		>
			<div class="p-1">
				<button
					v-for="entry in entries"
					:key="entry.pane"
					data-palette-item
					class="flow-palette-row"
					:aria-expanded="sub === entry.pane"
					@pointerenter="layout.narrow || (sub = entry.pane)"
					@click="sub = entry.pane"
				>
					<span class="size-4 flex-none" :class="entry.icon" aria-hidden="true" />
					<span class="min-w-0 flex-1 truncate">{{ entry.label }}</span>
					<span class="lucide-chevron-right flow-palette-hint size-4 flex-none" aria-hidden="true" />
				</button>
			</div>
		</PalettePanel>
		<ModelPalette
			v-if="sub === 'models'"
			dropdown
			:beside="beside"
			:width="LIST_WIDTH"
			:providers="providers"
			@close="close"
			@providers="openProviders"
		/>
		<ThinkingPalette
			v-else-if="sub === 'thinking'"
			dropdown
			:beside="beside"
			:width="LIST_WIDTH"
			@close="close"
		/>
	</span>
</template>

<script setup>
import { computed, inject, nextTick, ref, watch } from "vue"

import { layout } from "../layout.js"
import { EFFORT_LABELS, modelTitle } from "../transcript.js"
import ModelPalette from "./ModelPalette.vue"
import PalettePanel from "./PalettePanel.vue"
import ThinkingPalette from "./ThinkingPalette.vue"

// The composer's model button, with its own model and thinking lists; `open` asks the
// composer for its providers page, where an empty model list sends the user.
defineProps({ providers: { type: Boolean, default: false } })
const emit = defineEmits(["open"])
const flow = inject("flow")
const pane = ref(null) // null | "root"
const sub = ref(null) // null | "models" | "thinking", the list open beside the menu
// the models list's search goes when another list opens in its place: the keyboard stays in the
// chat, on the button, where a page's panel still hears its keys as the list's
watch(sub, (now, before) => {
	if (before === "models" && now === "thinking") nextTick(() => trigger.value?.focus({ preventScroll: true }))
})
const ROOT_WIDTH = 160
const LIST_WIDTH = 272
// the menu ends at the button's right edge and its list opens 4px past it, or 4px off the menu's
// left where the page has no room; a narrow frame's list takes the menu's place
const side = ref("right")
const beside = computed(() => (layout.narrow ? 0 : side.value === "right" ? -(LIST_WIDTH + 4) : ROOT_WIDTH + 4))
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
const entries = [
	{ pane: "models", label: "Model", icon: "lucide-cpu" },
	{ pane: "thinking", label: "Thinking", icon: "lucide-zap" },
]

function open() {
	const room = document.documentElement.clientWidth - trigger.value.parentElement.getBoundingClientRect().right
	side.value = room >= (LIST_WIDTH + 4 + 8) * layout.zoom ? "right" : "left"
	pane.value = "root"
}

function close() {
	pane.value = null
	sub.value = null
	nextTick(() => trigger.value?.focus())
}

function openProviders() {
	pane.value = null
	sub.value = null
	emit("open", "providers")
}
</script>
