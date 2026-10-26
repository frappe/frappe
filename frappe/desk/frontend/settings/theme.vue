<!-- The desk's colour scheme: light, dark or the system's. It applies at once and is kept in this browser. -->
<template>
	<div role="radiogroup" :aria-label="__('Theme')" class="mt-3 grid grid-cols-3 gap-3">
		<button
			v-for="scheme in SCHEMES"
			:key="scheme.value"
			type="button"
			role="radio"
			:aria-checked="colorScheme === scheme.value"
			:data-scheme="scheme.value"
			class="flex flex-col gap-2 rounded-4 p-1.5 pb-2 text-left outline-none ring-1 transition focus-visible:ring-2 focus-visible:ring-outline-gray-4"
			:class="
				colorScheme === scheme.value
					? 'ring-outline-gray-5'
					: 'ring-outline-gray-2 hover:ring-outline-gray-3'
			"
			@click="setColorScheme(scheme.value)"
		>
			<span class="flex h-16 overflow-hidden rounded-3 border border-outline-gray-2">
				<span
					v-for="half in scheme.halves"
					:key="half"
					class="flex flex-1 gap-1.5 p-2"
					:class="half"
				>
					<span class="w-3 rounded-1 bg-current opacity-20" />
					<span class="flex flex-1 flex-col gap-1.5">
						<span class="h-1.5 w-3/4 rounded-1 bg-current opacity-40" />
						<span class="h-1.5 w-1/2 rounded-1 bg-current opacity-20" />
					</span>
				</span>
			</span>
			<span class="flex items-center gap-1.5 px-0.5 text-base text-ink-gray-8">
				<span :class="scheme.icon" class="size-4 text-ink-gray-6" aria-hidden="true" />
				{{ scheme.label }}
			</span>
		</button>
	</div>
</template>

<script setup lang="ts">
import { useColorScheme } from "frappe-ui";
import { __ } from "frappe/i18n";

/** A block with no binding is handed an empty `bindings`. */
defineProps<{ bindings: Record<string, never> }>();

const LIGHT = "bg-white text-gray-900";
const DARK = "bg-gray-900 text-white";

const SCHEMES = [
	{ label: __("Light"), value: "light", icon: "lucide-sun", halves: [LIGHT] },
	{ label: __("Dark"), value: "dark", icon: "lucide-moon", halves: [DARK] },
	{ label: __("System"), value: "system", icon: "lucide-monitor", halves: [LIGHT, DARK] },
] as const;

const { colorScheme, setColorScheme } = useColorScheme();
</script>
