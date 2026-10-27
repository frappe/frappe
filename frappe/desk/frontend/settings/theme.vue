<!-- The desk's colour scheme: light, dark or the system's. It applies at once and is kept in this browser. -->
<template>
	<SettingsRow :title="__('Theme')">
		<Select
			class="w-56"
			:model-value="colorScheme"
			:options="SCHEMES"
			@update:model-value="(scheme) => setColorScheme(scheme as ColorScheme)"
		/>
	</SettingsRow>
</template>

<script setup lang="ts">
import { Select, SettingsRow, useColorScheme, type ColorScheme } from "frappe-ui";
import { __ } from "frappe/i18n";

/** A block with no binding is handed an empty `bindings`. */
defineProps<{ bindings: Record<string, never> }>();

const SCHEMES = [
	{ label: __("Light"), value: "light", icon: "lucide-sun" },
	{ label: __("Dark"), value: "dark", icon: "lucide-moon" },
	{ label: __("System"), value: "system", icon: "lucide-monitor" },
];

const { colorScheme, setColorScheme } = useColorScheme();
</script>
