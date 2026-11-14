<!--
  The utility slots, Search then Notifications: a rail cell each, or a panel row each.
-->
<template>
	<Tooltip v-if="form === 'cell'" side="right">
		<template #content>
			<span class="flex items-center gap-2 [&_[data-slot=key]]:text-ink-gray-4">
				{{ __("Search") }} <KeyboardShortcut combo="Mod+K" />
			</span>
		</template>
		<button
			type="button"
			data-key="palette-trigger"
			:class="CELL"
			:aria-label="__('Search')"
			aria-keyshortcuts="Control+K Meta+K"
			@click="openPalette"
		>
			<span class="lucide-search size-4" aria-hidden="true" />
		</button>
	</Tooltip>
	<button
		v-else
		type="button"
		data-key="palette-trigger"
		:class="ROW"
		aria-keyshortcuts="Control+K Meta+K"
		@click="openPalette"
	>
		<span class="lucide-search size-4" aria-hidden="true" />
		<span class="flex-1 truncate text-left">{{ __("Search") }}</span>
		<KeyboardShortcut combo="Mod+K" class="text-ink-gray-4" />
	</button>

	<slot name="notifications" :form="form" />
</template>

<script setup lang="ts">
import { KeyboardShortcut, Tooltip } from "frappe-ui";
import { __ } from "@/i18n";
import { openPalette } from "./palette";

defineProps<{ form: "cell" | "row" }>();

// `SidebarRailItem`'s `ghost` cell, whose own tooltip would put the key on a second line.
const CELL =
	"relative flex size-7 shrink-0 items-center justify-center rounded-4 text-base text-ink-gray-8 transition hover:bg-surface-gray-3 focus-visible:ring-0 focus-visible:focus-ring";
const ROW =
	"flex h-7 w-full items-center gap-2 rounded-4 px-2 text-sm text-ink-gray-8 transition hover:bg-surface-gray-3 focus-visible:ring-0 focus-visible:focus-ring";
</script>
