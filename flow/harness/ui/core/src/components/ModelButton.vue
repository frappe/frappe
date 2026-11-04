<template>
	<span class="relative min-w-0 max-w-[360px]">
		<!-- the row shrinks the wrapper; the button, sized to its text, must follow it. Its menu
		     nests the model and thinking lists, each opening on hover beside its row -->
		<Dropdown :options="options" align="end" side="top">
			<template #trigger>
				<Button
					variant="ghost"
					:size="large ? 'md' : 'sm'"
					class="max-w-full"
					:label="modelLabel"
					:title="`${currentModel ?? modelLabel} · thinking ${effortLabel}`"
				>
					<template v-if="currentEffort !== 'default'" #suffix>
						<span class="-ml-0.5 flex flex-none items-center gap-1.5">
							<span class="h-[3px] w-[3px] flex-none rounded-full bg-surface-gray-4" />
							<span class="text-ink-gray-5">{{ effortLabel }}</span>
						</span>
					</template>
				</Button>
			</template>
		</Dropdown>
	</span>
</template>

<script setup>
import { computed, inject } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue"

import { checked } from "../menu.js"
import { EFFORTS, EFFORT_LABELS, modelTitle } from "../transcript.js"

// The composer's model button: a menu whose Model and Thinking rows nest their lists; `open`
// asks the composer for its providers page, where an empty model list sends the user.
const props = defineProps({ providers: { type: Boolean, default: false }, large: { type: Boolean, default: false } })
const emit = defineEmits(["open"])
const flow = inject("flow")

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

// each provider's models under its name; none yet leads to connecting a provider
const modelOptions = computed(() => {
	const groups = new Map()
	for (const m of flow.state.models) {
		if (!groups.has(m.provider)) groups.set(m.provider, [])
		const option = { label: m.display_name || modelTitle(m.name), onClick: () => flow.selectModel(m.name) }
		groups.get(m.provider).push(checked(option, m.name === currentModel.value))
	}
	const lists = [...groups].map(([provider, options]) => ({ group: provider, options }))
	if (!lists.length) lists.push({ group: "none", hideLabel: true, options: [{ label: "No models yet", disabled: true }] })
	if (props.providers)
		lists.push({
			group: "providers",
			hideLabel: true,
			options: [{ label: "Connect a provider", icon: "lucide-key", onClick: () => emit("open", "providers") }],
		})
	return lists
})
const thinkingOptions = computed(() =>
	EFFORTS.map((id) => checked({ label: EFFORT_LABELS[id], onClick: () => flow.selectEffort(id) }, id === currentEffort.value)),
)
const options = computed(() => [
	{ label: "Model", icon: "lucide-cpu", submenu: modelOptions.value },
	{ label: "Thinking", icon: "lucide-zap", submenu: thinkingOptions.value },
])
</script>
