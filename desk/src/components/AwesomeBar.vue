<template>
	<Combobox nullable>
		<div class="relative w-80">
			<div class="absolute inset-y-0 left-0 flex items-center pl-4.5">
				<FeatherIcon name="search" class="h-4 w-4 text-gray-600" />
			</div>
			<ComboboxInput
				:placeholder="`Search or type a command (${searchShortcut})`"
				class="w-full rounded border-none bg-gray-100 py-1.5 pl-11.5 pr-4.5 text-base text-gray-800 placeholder-gray-500 focus:ring-0"
				autocomplete="off"
			/>
		</div>
	</Combobox>
</template>

<script setup lang="ts">
import { Combobox, ComboboxInput } from "@headlessui/vue"
import { FeatherIcon } from "frappe-ui"
import { computed } from "vue"

const searchShortcut = computed(() =>
	window.navigator.platform === "MacIntel" ? "⌘ + G" : "Ctrl + G"
)
</script>
