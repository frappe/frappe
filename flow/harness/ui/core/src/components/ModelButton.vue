<template>
	<span class="relative min-w-0">
		<button
			class="flex h-7 min-w-0 max-w-[360px] items-center gap-1.5 rounded-5 px-2 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-2"
			:class="menu ? 'bg-surface-gray-2' : ''"
			:title="`${currentModel ?? modelLabel} · thinking ${effortLabel}`"
			aria-haspopup="menu"
			:aria-expanded="menu"
			@click="menu = !menu"
		>
			<span class="min-w-0 truncate">{{ modelLabel }}</span>
			<template v-if="currentEffort !== 'default'">
				<span class="h-[3px] w-[3px] flex-none self-center rounded-full bg-surface-gray-4" />
				<span class="flex-none font-normal text-ink-gray-5">{{ effortLabel }}</span>
			</template>
			<FeatherIcon name="chevron-down" class="h-3 w-3 flex-none text-ink-gray-4" />
		</button>
		<PopMenu :open="menu" label="Model and thinking" :width="266" @close="menu = false">
			<button
				v-for="entry in entries"
				:key="entry.view"
				role="menuitem"
				class="flex w-full items-start gap-2.5 rounded-[10px] px-2.5 py-2 text-left hover:bg-surface-gray-2"
				@click="choose(entry.view)"
			>
				<FeatherIcon :name="entry.icon" class="h-3.5 w-3.5 flex-none self-center text-ink-gray-5" />
				<span class="min-w-0 flex-1">
					<span class="block text-xs font-medium leading-4 text-ink-gray-9">{{ entry.label }}</span>
					<span class="mt-1 block truncate text-2xs leading-4 text-ink-gray-5">{{ entry.value }}</span>
				</span>
				<FeatherIcon name="chevron-right" class="h-3.5 w-3.5 flex-none self-center text-ink-gray-4" />
			</button>
		</PopMenu>
	</span>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { EFFORT_LABELS } from "../transcript.js"
import PopMenu from "./PopMenu.vue"

// The composer's model button: a menu of the model and thinking palettes, which
// the composer owns — `open` names the one to show.
const emit = defineEmits(["open"])
const flow = inject("flow")
const menu = ref(false)

const currentModel = computed(() => flow.state.conversation.model ?? flow.state.prefs.lastModel)
const currentEffort = computed(
	() => flow.state.conversation.reasoningEffort ?? flow.state.prefs.lastEffort ?? "default",
)
// The button shows only the final model id; routed names can have multiple
// namespace segments (for example openrouter/openai/gpt).
const modelLabel = computed(() => {
	const model = currentModel.value
	if (!model) return "Choose Model"
	return model.split("/").filter(Boolean).pop() || model
})
const effortLabel = computed(() => EFFORT_LABELS[currentEffort.value] ?? "Default")
const entries = computed(() => [
	{ view: "models", label: "Model", icon: "cpu", value: modelLabel.value },
	{ view: "thinking", label: "Thinking", icon: "zap", value: effortLabel.value },
])

function choose(view) {
	menu.value = false
	emit("open", view)
}
</script>
