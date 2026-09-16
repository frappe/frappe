<template>
	<SettingsDialog
		v-model:tab="active"
		size="6xl"
		:shortcut="false"
		:open="flow.state.settingsOpen"
		@update:open="flow.setSettingsOpen($event)"
	>
		<SettingsSidebar class="sm:pt-3">
			<SettingsNavGroup v-for="(group, i) in groups" :key="i">
				<template v-if="group.label" #label>
					<span class="mb-1 block text-2xs font-medium text-ink-gray-7">{{ group.label }}</span>
					<!-- phones have no Escape key: the first label row carries a way out -->
					<button
						v-if="i === 0"
						class="flow-icon-btn ml-auto sm:hidden"
						title="Close"
						@click="flow.setSettingsOpen(false)"
					>
						<FeatherIcon name="x" class="h-4 w-4" />
					</button>
				</template>
				<SettingsNavItem v-for="item in group.tabs" :key="item.id" :value="item.id" class="text-xs">
					<template #prefix>
						<FeatherIcon :name="item.icon" class="h-4 w-4 text-ink-gray-6" />
					</template>
					{{ item.label }}
				</SettingsNavItem>
			</SettingsNavGroup>
		</SettingsSidebar>

		<!-- min-w-0 on the pane and each panel: long unbreakable content (paths)
		     must not widen them past the dialog -->
		<SettingsContent class="min-w-0">
			<SettingsPanel v-for="item in tabs" :key="item.id" :value="item.id" class="min-w-0">
				<slot :name="item.id" />
			</SettingsPanel>
		</SettingsContent>
	</SettingsDialog>
</template>

<script setup>
import { computed, inject } from "vue"
import {
	SettingsContent,
	SettingsDialog,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsPanel,
	SettingsSidebar,
} from "frappe-ui/src/components/SettingsDialog"
import FeatherIcon from "./FeatherIcon.vue"

// The settings shell: the dialog, its sidebar and its type scale are shared. A host
// names its tabs in `groups` and fills one slot per tab id with its own panel.
const props = defineProps({
	groups: { type: Array, required: true }, // [{ label, tabs: [{ id, label, icon }] }]
})
const tab = defineModel("tab", { type: String, default: undefined })
const flow = inject("flow")

const tabs = computed(() => props.groups.flatMap((group) => group.tabs))
const active = computed({
	get: () => tab.value ?? tabs.value[0]?.id,
	set: (value) => (tab.value = value),
})
</script>

<style scoped>
/* field labels read like the section titles next to them */
:deep([data-slot="label"]) {
	color: var(--ink-gray-9);
	font-weight: 500;
}
/* one step below frappe-ui's default control size, matching the panels' text */
:deep([data-slot="label"]),
:deep([data-slot="control"]),
:deep([data-slot="trigger"]) {
	font-size: 14px;
}
/* iPhone Safari zooms into fields set below 16px */
@media (max-width: 639px) {
	:deep([data-slot="control"]) {
		font-size: 16px;
	}
}
</style>
