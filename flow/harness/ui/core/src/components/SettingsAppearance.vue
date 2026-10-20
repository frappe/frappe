<template>
	<SettingsPage title="Appearance" description="How Flow looks.">
		<template #actions>
			<Button label="Reset to defaults" :disabled="isDefault" @click="reset" />
		</template>
		<div class="divide-y divide-outline-gray-1">
			<SettingsRow title="Theme" description="Follow the system, or pick one.">
				<Select :model-value="colorScheme" :options="THEMES" class="w-36" @update:model-value="setColorScheme" />
			</SettingsRow>
			<SettingsRow title="Font size" description="The size of the chat's text." :saved="size">
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
							aria-label="Font size"
							class="min-w-0 flex-1 border-0 bg-transparent py-0 pl-2 pr-0 text-sm tabular-nums text-ink-gray-8 [appearance:textfield] focus:ring-0 [&::-webkit-inner-spin-button]:appearance-none"
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
								<FeatherIcon :name="step.icon" class="h-3 w-3" />
							</button>
						</span>
					</span>
					<span class="text-sm text-ink-gray-6">px</span>
				</span>
			</SettingsRow>
			<SettingsRow title="Font weight" description="The weight of the chat's text." :saved="weight">
				<Select
					:model-value="weight"
					:options="CHAT_FONT_WEIGHT.options"
					class="w-36"
					@update:model-value="flow.setChatFontWeight"
				/>
			</SettingsRow>
		</div>
	</SettingsPage>
</template>

<script setup>
import { computed, inject } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import { Select } from "frappe-ui/src/components/Select"
import { useColorScheme } from "frappe-ui/src/composables/useColorScheme"
import FeatherIcon from "./FeatherIcon.vue"

import { CHAT_FONT_SIZE, CHAT_FONT_WEIGHT } from "../layout.js"
import SettingsPage from "./SettingsPage.vue"
import SettingsRow from "./SettingsRow.vue"

const THEMES = [
	{ label: "System", value: "system" },
	{ label: "Light", value: "light" },
	{ label: "Dark", value: "dark" },
]
const STEPS = [
	{ by: 1, icon: "chevron-up", title: "Increase font size" },
	{ by: -1, icon: "chevron-down", title: "Decrease font size" },
]
const flow = inject("flow")
const { colorScheme, setColorScheme } = useColorScheme()
const size = computed(() => flow.state.prefs.chatFontSize)
const weight = computed(() => flow.state.prefs.chatFontWeight)

const isDefault = computed(
	() => colorScheme.value === "system" && size.value === CHAT_FONT_SIZE.default && weight.value === CHAT_FONT_WEIGHT.default,
)
function reset() {
	setColorScheme("system")
	flow.setChatFontSize(CHAT_FONT_SIZE.default)
	flow.setChatFontWeight(CHAT_FONT_WEIGHT.default)
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
