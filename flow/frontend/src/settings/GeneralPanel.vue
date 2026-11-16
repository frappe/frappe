<template>
	<component
		:is="siteSettings ? DocForm : SettingsPage"
		v-bind="siteSettings ? { spec: SPECS.flow_settings, rows: true } : {}"
		:title="__('General')"
		:description="
			siteSettings
				? __('Your account and site settings.')
				: __('Your account and how Flow looks.')
		"
	>
		<div class="divide-y divide-outline-gray-1">
			<SettingsRow :title="__('Signed in as')" :description="user.name">
				<span class="flex items-center gap-2 text-base text-ink-gray-8">
					<Avatar :image="user.user_image" :label="user.full_name" size="sm" />
					{{ user.full_name }}
				</span>
			</SettingsRow>
			<!-- in a page's panel the page owns the theme, which the chat follows -->
			<SettingsRow v-if="!inPanel" :title="__('Theme')" :description="__('Follow the system, or pick one.')">
				<Select
					:model-value="colorScheme"
					:options="THEMES"
					class="w-36"
					@update:model-value="setColorScheme"
				/>
			</SettingsRow>
			<SettingsRow :title="__('Show each step separately')" :description="__('When off, steps are grouped into one line.')">
				<Switch
					:model-value="flow.state.prefs.separateToolCalls"
					:aria-label="__('Show each step separately')"
					@update:model-value="flow.setSeparateToolCalls"
				/>
			</SettingsRow>
		</div>
	</component>
</template>

<script setup>
import { computed, inject } from "vue";
import { Avatar, Select, Switch, useColorScheme } from "frappe-ui";
import SettingsPage from "@flow/ui-core/components/SettingsPage.vue";
import SettingsRow from "@flow/ui-core/components/SettingsRow.vue";
import { __ } from "@flow/ui-core/translate.js";

import { inPanel } from "../panel.js";
import DocForm from "./DocForm.vue";
import { SPECS } from "./specs.js";

const THEMES = [
	{ label: __("System"), value: "system" },
	{ label: __("Light"), value: "light" },
	{ label: __("Dark"), value: "dark" },
];
const flow = inject("flow");
const page = inject("flowPage");
const user = computed(() => page.state.boot.user ?? { name: "", full_name: "" });
const siteSettings = computed(() => page.can("Flow Settings", "read"));
const { colorScheme, setColorScheme } = inPanel ? {} : useColorScheme();
</script>
