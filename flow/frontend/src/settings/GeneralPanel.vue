<template>
	<component
		:is="siteSettings ? DocForm : SettingsPage"
		v-bind="siteSettings ? { spec: SPECS.flow_settings, rows: true } : {}"
		title="General"
		:description="
			siteSettings
				? 'Your account, how Flow looks, and settings for everyone.'
				: 'Your account and how Flow looks.'
		"
	>
		<div class="divide-y divide-outline-gray-1">
			<SettingsRow title="Signed in as" :description="user.name">
				<span class="flex items-center gap-2 text-base text-ink-gray-8">
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
		</div>
	</component>
</template>

<script setup>
import { computed, inject } from "vue";
import { Avatar, Select, useColorScheme } from "frappe-ui";
import SettingsPage from "@flow/ui-core/components/SettingsPage.vue";
import SettingsRow from "@flow/ui-core/components/SettingsRow.vue";

import DocForm from "./DocForm.vue";
import { SPECS } from "./specs.js";

const THEMES = [
	{ label: "System", value: "system" },
	{ label: "Light", value: "light" },
	{ label: "Dark", value: "dark" },
];
const page = inject("flowPage");
const user = computed(() => page.state.boot.user ?? { name: "", full_name: "" });
const siteSettings = computed(() => page.can("Flow Settings", "read"));
const { colorScheme, setColorScheme } = useColorScheme();
</script>
