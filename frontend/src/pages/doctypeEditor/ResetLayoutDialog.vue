<!-- Reset to app layout: the site layouts of a type it removes and what comes back after the
     save. It closes with `true` to reset. -->
<template>
	<div class="flex flex-col gap-4 text-p-base text-ink-gray-7" data-reset-layout-dialog>
		<div class="flex flex-col gap-2">
			<p>{{ __("Removes this site's {0} layouts:", [label]) }}</p>
			<ul class="flex flex-col gap-1.5" data-reset-removes>
				<li
					v-for="(row, index) in summary.removes"
					:key="index"
					class="flex items-center gap-2"
				>
					<Icon name="lucide-minus" class="size-4 shrink-0 text-ink-gray-5" />
					<span class="truncate">{{ row.name }}</span>
					<span
						v-if="row.condition && row.condition !== row.name"
						class="truncate text-ink-gray-5"
					>
						{{ row.condition }}
					</span>
				</li>
			</ul>
		</div>
		<div v-if="summary.restores.length" class="flex flex-col gap-2">
			<p>{{ __("After you save, the app's layouts come back:") }}</p>
			<ul class="flex flex-col gap-1.5" data-reset-restores>
				<li
					v-for="(row, index) in summary.restores"
					:key="index"
					class="flex items-center gap-2"
				>
					<Icon name="lucide-plus" class="size-4 shrink-0 text-ink-gray-5" />
					<span class="truncate">{{ row.name }}</span>
				</li>
			</ul>
		</div>
		<p v-else>{{ __("After you save, {0} goes back to: {1}.", [label, summary.fallback]) }}</p>
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" @click="close(null)" />
			<Button variant="solid" :label="__('Reset to app layout')" @click="close(true)" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, Icon } from "frappe-ui";
import { __ } from "@/i18n";
import type { ResetSummary } from "./layoutMenu";

defineProps<{ label: string; summary: ResetSummary; close: (reset: true | null) => void }>();
</script>
