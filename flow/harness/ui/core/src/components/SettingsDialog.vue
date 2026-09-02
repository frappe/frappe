<template>
	<SettingsDialog
		v-model:tab="tab"
		size="6xl"
		:shortcut="false"
		:open="flow.state.settingsOpen"
		@update:open="flow.setSettingsOpen($event)"
	>
		<SettingsSidebar class="sm:pt-3">
			<SettingsNavGroup>
				<template #label>
					<span class="mb-1 block text-xs font-medium text-ink-gray-7">Settings</span>
				</template>
				<SettingsNavItem v-for="s in SECTIONS" :key="s.id" :value="s.id" class="h-8 gap-2.5 px-3 text-sm">
					<template #prefix>
						<FeatherIcon :name="s.icon" class="h-4 w-4 text-ink-gray-6" />
					</template>
					{{ s.label }}
				</SettingsNavItem>
			</SettingsNavGroup>
		</SettingsSidebar>

		<!-- min-w-0 on the pane and each panel: long unbreakable content (paths)
		     must not widen them past the dialog -->
		<SettingsContent class="min-w-0">
			<SettingsPanel value="general" class="min-w-0">
				<div class="min-h-0 flex-1 overflow-y-auto px-8 pb-10 pt-8">
					<h2 class="text-xl font-semibold text-ink-gray-9">General</h2>
					<p class="mt-1 text-sm leading-5 text-ink-gray-6">Defaults for new chats.</p>

					<div class="mt-4 divide-y divide-outline-gray-1">
						<div class="flex items-center gap-8 py-4">
							<div class="min-w-0 flex-1">
								<div class="text-base font-medium text-ink-gray-9">Approval mode</div>
								<p class="mt-1.5 text-sm leading-5 text-ink-gray-6">Applies to new chats and the current one.</p>
							</div>
							<Select :model-value="flow.state.prefs.mode" :options="MODES" @update:model-value="flow.setMode($event)" />
						</div>

						<div class="py-4">
							<div class="text-base font-medium text-ink-gray-9">Custom instructions</div>
							<p class="mt-1.5 text-sm leading-5 text-ink-gray-6">
								Added to the prompt of every new chat.
							</p>
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
				</div>
			</SettingsPanel>

			<SettingsPanel value="skills" class="min-w-0">
				<SettingsSkills />
			</SettingsPanel>

			<SettingsPanel value="appearance" class="min-w-0">
				<div class="min-h-0 flex-1 overflow-y-auto px-8 pb-10 pt-8">
					<h2 class="text-xl font-semibold text-ink-gray-9">Appearance</h2>
					<p class="mt-1 text-sm leading-5 text-ink-gray-6">Pick a theme.</p>

					<div class="mt-4 py-4">
						<div class="text-base font-medium text-ink-gray-9">Theme</div>
						<p class="mt-1.5 text-sm leading-5 text-ink-gray-6">Switch between light, dark, or system theme.</p>
						<!-- own heading above: the switcher's built-in one uses a smaller type scale -->
						<ThemeSwitcher class="flow-theme-switcher mt-4" label="" description="" name="Flow" />
					</div>
				</div>
			</SettingsPanel>
		</SettingsContent>
	</SettingsDialog>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import { Select } from "frappe-ui/src/components/Select"
import {
	SettingsContent,
	SettingsDialog,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsPanel,
	SettingsSidebar,
} from "frappe-ui/src/components/SettingsDialog"
import { Textarea } from "frappe-ui/src/components/Textarea"
import { ThemeSwitcher } from "frappe-ui/src/components/ThemeSwitcher"
import FeatherIcon from "./FeatherIcon.vue"
import SettingsSkills from "./SettingsSkills.vue"

const flow = inject("flow")
const tab = ref("general")

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

const SECTIONS = [
	{ id: "general", label: "General", icon: "sliders" },
	{ id: "appearance", label: "Appearance", icon: "sun" },
	{ id: "skills", label: "Skills", icon: "book-open" },
]
const MODES = [
	{ label: "Ask for approval", value: "ask" },
	{ label: "Auto-approve", value: "auto" },
]
</script>

<style scoped>
/* field labels read like the section titles next to them */
:deep([data-slot="label"]) {
	color: var(--ink-gray-9);
	font-weight: 500;
}
/* desk layout: cards share the row evenly at equal height, System first */
.flow-theme-switcher :deep([data-slot="control"]) {
	align-items: stretch;
}
.flow-theme-switcher :deep([data-slot="option"]) {
	display: flex;
	flex-direction: column;
	max-width: none;
}
.flow-theme-switcher :deep([data-slot="option"] > :first-child) {
	flex: 1;
}
.flow-theme-switcher :deep([data-theme-option="system"]) {
	order: -1;
}
.flow-theme-switcher :deep([data-theme-option="system"] [class*="max-h-"]) {
	max-height: none;
}
</style>
