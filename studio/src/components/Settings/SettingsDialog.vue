<template>
	<SettingsDialog v-model:open="store.showSettingsDialog" v-model:tab="store.settingsTab" size="3xl">
		<SettingsSidebar>
			<SettingsNavGroup label="Settings">
				<SettingsNavItem value="app">
					<template #prefix><span class="lucide-app-window size-4" /></template>
					App
				</SettingsNavItem>
				<SettingsNavItem value="editor">
					<template #prefix><span class="lucide-sliders-vertical size-4" /></template>
					Editor
				</SettingsNavItem>
			</SettingsNavGroup>
		</SettingsSidebar>
		<SettingsContent>
			<SettingsPanel value="app">
				<AppSettings v-if="store.activeApp" />
			</SettingsPanel>
			<SettingsPanel value="editor">
				<EditorSettings />
			</SettingsPanel>
		</SettingsContent>
	</SettingsDialog>
</template>

<script setup lang="ts">
import {
	SettingsDialog,
	SettingsSidebar,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsContent,
	SettingsPanel,
} from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import AppSettings from "@/components/Settings/AppSettings.vue"
import EditorSettings from "@/components/Settings/EditorSettings.vue"

const store = useStudioStore()
</script>
