<template>
	<SettingsPage title="General" description="Defaults for new chats.">
		<div class="divide-y divide-outline-gray-1">
			<SettingsRow title="Approval mode" description="Applies to new chats and the current one.">
				<Select :model-value="flow.state.prefs.mode" :options="MODES" @update:model-value="flow.setMode($event)" />
			</SettingsRow>
			<SettingsRow title="Helper model" description="Does quick side jobs, like chat titles. A cheaper model saves credits.">
				<Combobox
					:model-value="flow.state.prefs.smallModel ?? ''"
					:options="smallModels"
					placeholder="The chat's model"
					align="end"
					class="w-48"
					@update:model-value="flow.setSmallModel($event)"
				>
					<template #item-label="{ item }">
						<div class="max-w-64 truncate leading-tighter" :title="item.label">{{ item.label }}</div>
					</template>
				</Combobox>
			</SettingsRow>
			<SettingsRow title="Web search" description="The service agents use to search the web.">
				<div class="flex items-center gap-2">
					<KeyButton
						v-if="provider !== 'duckduckgo'"
						:key="provider"
						:label="`${providerOption.label} API key`"
						:link="providerOption.link"
						:saved="keySaved"
						@save="saveSearchKey"
						@cancel="provider = flow.state.prefs.webSearch?.provider ?? 'duckduckgo'"
					/>
					<Select :model-value="provider" :options="SEARCH_PROVIDERS" class="w-48" @update:model-value="pickProvider" />
				</div>
			</SettingsRow>
			<div class="py-4">
				<div class="text-base font-medium text-ink-gray-9">Custom instructions</div>
				<p class="mt-1.5 text-sm leading-5 text-ink-gray-6">Added to the prompt of every new chat.</p>
				<Textarea
					v-model="draft"
					class="mt-4"
					:rows="8"
					placeholder="Reply in short sentences. Prefer Python over shell scripts."
				/>
				<div class="mt-3 flex justify-end">
					<Button variant="solid" label="Save" :disabled="!dirty" @click="save" />
				</div>
			</div>
		</div>
	</SettingsPage>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import { Combobox } from "frappe-ui/src/components/Combobox"
import { Select } from "frappe-ui/src/components/Select"
import { Textarea } from "frappe-ui/src/components/Textarea"

import { APPROVAL_MODES, modelTitle } from "../transcript.js"
import KeyButton from "./KeyButton.vue"
import SettingsPage from "./SettingsPage.vue"
import SettingsRow from "./SettingsRow.vue"

const flow = inject("flow")
const MODES = APPROVAL_MODES.map((mode) => ({ label: mode.label, value: mode.id }))
const smallModels = computed(() => [
	{ label: "The chat's model", value: "" },
	...flow.state.models.map((model) => ({ label: modelTitle(model.name, flow.state.models), value: model.name })),
])

// instructions are a draft until saved; reopening discards unsaved edits
const draft = ref(flow.state.prefs.customInstructions)
const dirty = computed(() => draft.value !== flow.state.prefs.customInstructions)
watch(
	() => flow.state.settingsOpen,
	(open) => {
		if (open) draft.value = flow.state.prefs.customInstructions
	},
)
const SEARCH_PROVIDERS = [
	{ label: "DuckDuckGo", value: "duckduckgo" },
	{ label: "Brave", value: "brave", link: "https://brave.com/search/api/" },
	{ label: "Tavily", value: "tavily", link: "https://app.tavily.com" },
	{ label: "Exa", value: "exa", link: "https://dashboard.exa.ai/api-keys" },
]
const provider = ref("duckduckgo")
const keySaved = computed(() => flow.state.prefs.webSearch?.provider === provider.value)
const providerOption = computed(() => SEARCH_PROVIDERS.find((p) => p.value === provider.value))
watch(
	() => flow.state.settingsOpen,
	(open) => {
		if (!open) return
		provider.value = flow.state.prefs.webSearch?.provider ?? "duckduckgo"
	},
	{ immediate: true },
)
// a provider that needs a key is saved once its key is in
function pickProvider(value) {
	provider.value = value
	if (value === "duckduckgo") {
		flow.setWebSearch(null)
		flow.notify("Web search saved")
	}
}
function saveSearchKey(key) {
	flow.setWebSearch({ provider: provider.value, api_key: key })
	flow.notify("Web search saved")
}
function save() {
	flow.setCustomInstructions(draft.value)
	flow.notify("Custom instructions saved")
}
</script>
