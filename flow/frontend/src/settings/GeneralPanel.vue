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
		</div>
	</SettingsPage>
</template>

<script setup>
import { computed, inject } from "vue";
import { Avatar, Select, useColorScheme } from "frappe-ui";
import SettingsPage from "@flow/ui-core/components/SettingsPage.vue";
import SettingsRow from "@flow/ui-core/components/SettingsRow.vue";

const THEMES = [
	{ label: "System", value: "system" },
	{ label: "Light", value: "light" },
	{ label: "Dark", value: "dark" },
];
const page = inject("flowPage");
const user = computed(() => page.state.boot.user ?? { name: "", full_name: "" });
const { colorScheme, setColorScheme } = useColorScheme();
</script>
