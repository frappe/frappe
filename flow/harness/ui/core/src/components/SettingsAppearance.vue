<template>
	<SettingsPage :title="__('Appearance')" :description="__('How Flow looks.')">
		<template #actions>
			<Button :label="__('Reset to defaults')" :disabled="isDefault" @click="reset" />
		</template>
		<div class="divide-y divide-outline-gray-1">
			<SettingsRow :title="__('Theme')" :description="__('Follow the system, or pick one.')">
				<Select align="start" :model-value="colorScheme" :options="THEMES" class="w-36" @update:model-value="setColorScheme" />
			</SettingsRow>
			<SettingsRow :title="__('Font size')" :description="FONT_SIZE_HELP" :saved="size">
				<span class="flex items-center gap-2">
					<!-- one box: the steps sit inside its border and round with its corners -->
					<span
						class="flex h-7 w-20 rounded-4 border border-[--surface-gray-2] bg-surface-gray-2 transition-colors hover:border-outline-elevation-2 hover:bg-surface-gray-3 has-[input:focus]:border-outline-gray-4 has-[input:focus]:bg-surface-base has-[input:focus]:shadow-sm"
					>
						<input
							:value="size"
							type="number"
							:min="CHAT_FONT_SIZE.min"
							:max="CHAT_FONT_SIZE.max"
							step="any"
							:aria-label="__('Font size')"
							class="min-w-0 flex-1 border-0 bg-transparent py-0 pl-2 pr-0 text-base tabular-nums text-ink-gray-8 [appearance:textfield] focus:ring-0 [&::-webkit-inner-spin-button]:appearance-none"
							@input="preview"
							@change="commit"
						/>
						<span class="flex w-5 flex-none flex-col">
							<button
								v-for="step in STEPS"
								:key="step.by"
								class="grid flex-1 place-items-center text-ink-gray-6 first:rounded-tr-[7px] last:rounded-br-[7px] enabled:hover:bg-surface-gray-4 enabled:hover:text-ink-gray-9 disabled:text-ink-gray-3"
								:title="step.title"
								:disabled="step.by > 0 ? size >= CHAT_FONT_SIZE.max : size <= CHAT_FONT_SIZE.min"
								@click="flow.setChatFontSize(size + step.by)"
							>
								<span class="size-3" :class="step.icon" aria-hidden="true" />
							</button>
						</span>
					</span>
					<span class="text-base text-ink-gray-6">px</span>
				</span>
			</SettingsRow>
			<SettingsRow :title="__('Font weight')" :description="FONT_WEIGHT_HELP" :saved="weight">
				<Select
					align="start"
					:model-value="weight"
					:options="CHAT_FONT_WEIGHT.options"
					class="w-36"
					@update:model-value="flow.setChatFontWeight"
				/>
			</SettingsRow>
			<SettingsRow :title="__('Show each step separately')" :description="__('When off, steps are grouped into one line.')">
				<Switch :model-value="separateToolCalls" :aria-label="__('Show each step separately')" @update:model-value="flow.setSeparateToolCalls" />
			</SettingsRow>
		</div>
	</SettingsPage>
</template>

<script setup>
import { computed, inject } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import { Select } from "frappe-ui/src/components/Select"
import { Switch } from "frappe-ui/src/components/Switch"
import { useColorScheme } from "frappe-ui/src/composables/useColorScheme"

import { CHAT_FONT_SIZE, CHAT_FONT_WEIGHT } from "../layout.js"
import { __ } from "../translate.js"
import SettingsPage from "./SettingsPage.vue"
import SettingsRow from "./SettingsRow.vue"

const THEMES = [
	{ label: __("System"), value: "system" },
	{ label: __("Light"), value: "light" },
	{ label: __("Dark"), value: "dark" },
]
const STEPS = [
	{ by: 1, icon: "lucide-chevron-up", title: __("Increase font size") },
	{ by: -1, icon: "lucide-chevron-down", title: __("Decrease font size") },
]
const FONT_SIZE_HELP = __("The size of the chat's text. The rest of Flow scales with it.")
const FONT_WEIGHT_HELP = __("The weight of the chat's text.")
const flow = inject("flow")
const { colorScheme, setColorScheme } = useColorScheme()
const size = computed(() => flow.state.prefs.chatFontSize)
const weight = computed(() => flow.state.prefs.chatFontWeight)
const separateToolCalls = computed(() => flow.state.prefs.separateToolCalls)

const isDefault = computed(
	() =>
		colorScheme.value === "system" &&
		size.value === CHAT_FONT_SIZE.default &&
		weight.value === CHAT_FONT_WEIGHT.default &&
		!separateToolCalls.value,
)
function reset() {
	setColorScheme("system")
	flow.setChatFontSize(CHAT_FONT_SIZE.default)
	flow.setChatFontWeight(CHAT_FONT_WEIGHT.default)
	flow.setSeparateToolCalls(false)
}

// a typed size applies as soon as it's complete and in range ("14." and "14.0" may be on their
// way to 14.05); Enter or leaving the box clamps one out of range and puts back a non-number
function preview(event) {
	const px = event.target.valueAsNumber
	if (String(px) === event.target.value && px >= CHAT_FONT_SIZE.min && px <= CHAT_FONT_SIZE.max) flow.setChatFontSize(px)
}
function commit(event) {
	const px = event.target.valueAsNumber
	if (Number.isFinite(px)) flow.setChatFontSize(px)
	event.target.value = size.value
}
</script>
