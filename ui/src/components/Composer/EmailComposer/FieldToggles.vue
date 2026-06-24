<template>
	<!-- Header buttons that reveal the optional email rows. To and Subject are
		 prop-driven (always shown when present), so only Cc/Bcc are toggles here.
		 Which buttons appear is set by `optionalFields`. -->
	<Button
		v-if="optionalFields.includes('cc')"
		variant="ghost"
		label="CC"
		:class="showCc ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
		@click="emit('toggle-cc')"
	/>
	<Button
		v-if="optionalFields.includes('bcc')"
		variant="ghost"
		label="BCC"
		:class="showBcc ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
		@click="emit('toggle-bcc')"
	/>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import type { OptionalField } from "../types";

withDefaults(
	defineProps<{
		optionalFields?: OptionalField[];
		showCc?: boolean;
		showBcc?: boolean;
	}>(),
	{
		optionalFields: () => ["cc", "bcc"],
		showCc: false,
		showBcc: false,
	}
);

const emit = defineEmits<{
	"toggle-cc": [];
	"toggle-bcc": [];
}>();
</script>
