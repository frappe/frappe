<template>
	<SettingsPage title="General" description="Defaults for new chats.">
		<div class="divide-y divide-outline-gray-1">
			<SettingsRow title="Approval mode" description="Applies to new chats and the current one.">
				<Select :model-value="flow.state.prefs.mode" :options="MODES" @update:model-value="flow.setMode($event)" />
			</SettingsRow>
			<div class="py-4">
				<div class="text-sm font-medium text-ink-gray-9">Custom instructions</div>
				<p class="mt-1.5 text-xs leading-5 text-ink-gray-6">Added to the prompt of every new chat.</p>
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
import { Select } from "frappe-ui/src/components/Select"
import { Textarea } from "frappe-ui/src/components/Textarea"

import { APPROVAL_MODES } from "../transcript.js"
import SettingsPage from "./SettingsPage.vue"
import SettingsRow from "./SettingsRow.vue"

const flow = inject("flow")
const MODES = APPROVAL_MODES.map((mode) => ({ label: mode.label, value: mode.id }))

// instructions are a draft until saved; reopening discards unsaved edits
const draft = ref(flow.state.prefs.customInstructions)
const dirty = computed(() => draft.value !== flow.state.prefs.customInstructions)
watch(
	() => flow.state.settingsOpen,
	(open) => {
		if (open) draft.value = flow.state.prefs.customInstructions
	},
)
function save() {
	flow.setCustomInstructions(draft.value)
	flow.notify("Custom instructions saved")
}
</script>
