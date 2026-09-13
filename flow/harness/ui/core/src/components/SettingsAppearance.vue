<template>
	<SettingsPage title="Appearance" description="Pick a theme.">
		<div class="py-4">
			<div class="text-sm font-medium text-ink-gray-9">Theme</div>
			<p class="mt-1.5 text-xs leading-5 text-ink-gray-6">Switch between light, dark, or system theme.</p>
			<!-- own heading above: the switcher's built-in one uses a smaller type scale -->
			<ThemeSwitcher class="flow-theme-switcher mt-4" label="" description="" name="Flow" />
		</div>
	</SettingsPage>
</template>

<script setup>
import { ThemeSwitcher } from "frappe-ui/src/components/ThemeSwitcher"

import SettingsPage from "./SettingsPage.vue"
</script>

<style scoped>
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
