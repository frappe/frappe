<!-- One palette row: icon, label, gray description, and the act's key on the right. -->
<template>
	<CommandPaletteItem :value="row" :disabled="row.pending" class="gap-2.5" :data-row="row.id">
		<template #prefix>
			<LoadingIndicator v-if="row.pending" class="size-4 shrink-0 text-ink-gray-5" />
			<span
				v-else
				:class="[row.icon, 'size-4 shrink-0 text-ink-gray-6']"
				aria-hidden="true"
			/>
		</template>
		{{ row.label }}
		<span v-if="row.description" class="pl-1.5 font-normal text-ink-gray-5">{{
			row.description
		}}</span>
		<template v-if="row.key" #suffix>
			<!-- A flex box and its own `leading-none`, or the key's `text-sm` line makes the row 1.5px taller. -->
			<span class="flex"><KeyboardShortcut :combo="row.key" class="leading-none" /></span>
		</template>
	</CommandPaletteItem>
</template>

<script setup lang="ts">
import { KeyboardShortcut, LoadingIndicator } from "frappe-ui";
import { CommandPaletteItem } from "frappe-ui/experimental";
import type { PaletteRow } from "./palette";

defineProps<{ row: PaletteRow }>();
</script>
