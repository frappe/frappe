<template>
	<SettingsPage title="General" description="Your account and how Flow looks.">
		<div class="divide-y divide-outline-gray-1">
			<SettingsRow title="Signed in as" :description="user.name">
				<span class="flex items-center gap-2 text-sm text-ink-gray-8">
					<Avatar :image="user.user_image" :label="user.full_name" size="sm" />
					{{ user.full_name }}
				</span>
			</SettingsRow>
			<SettingsRow title="Theme" description="Follow the system, or pick one.">
				<Select
					:model-value="colorScheme"
					:options="THEMES"
					class="w-36"
					@update:model-value="setColorScheme"
				/>
			</SettingsRow>
			<SettingsRow title="Flow icon" description="Opens Flow beside your work in Desk and other apps.">
				<Switch :model-value="!page.state.boot.launcher_hidden" @update:model-value="showLauncher" />
			</SettingsRow>
		</div>
	</SettingsPage>
</template>

<script setup>
import { computed, inject } from "vue";
import { Avatar, Select, Switch, toast, useColorScheme } from "frappe-ui";
import SettingsPage from "@flow/ui-core/components/SettingsPage.vue";
import SettingsRow from "@flow/ui-core/components/SettingsRow.vue";

import { call } from "../api/frappe.js";

const THEMES = [
	{ label: "System", value: "system" },
	{ label: "Light", value: "light" },
	{ label: "Dark", value: "dark" },
];
const page = inject("flowPage");
const user = computed(() => page.state.boot.user ?? { name: "", full_name: "" });
const { colorScheme, setColorScheme } = useColorScheme();

// app pages follow on their next load; the launcher around this page, at once
async function showLauncher(shown) {
	page.state.boot.launcher_hidden = !shown;
	try {
		await call("frappe.flow.launcher.set_hidden", { hidden: !shown });
		window.dispatchEvent(new CustomEvent("flow-launcher", { detail: { hidden: !shown } }));
	} catch (error) {
		page.state.boot.launcher_hidden = shown;
		toast.error(error.message);
	}
}
</script>
