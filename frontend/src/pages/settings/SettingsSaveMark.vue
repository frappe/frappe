<!-- A row's quiet save mark, Saving…, Saved or Not saved, in a width that is always held. -->
<template>
	<span class="flex w-20 shrink-0 justify-end" aria-live="polite">
		<span
			v-if="mark"
			class="inline-flex items-center gap-1 whitespace-nowrap text-sm"
			:class="mark === 'error' ? 'text-ink-red-7' : 'text-ink-gray-5'"
		>
			<LoadingIndicator v-if="mark === 'saving'" class="size-3" />
			<span v-else-if="mark === 'saved'" class="lucide-check size-3.5" aria-hidden="true" />
			<span v-else class="lucide-circle-alert size-3.5" aria-hidden="true" />
			{{ TEXT[mark] }}
		</span>
	</span>
</template>

<script setup lang="ts">
import { LoadingIndicator } from "frappe-ui";
import { __ } from "@/i18n";
import type { RowMark } from "./bindingDraft";

defineProps<{ mark?: RowMark }>();

const TEXT: Record<RowMark, string> = {
	saving: __("Saving…"),
	saved: __("Saved"),
	error: __("Not saved"),
};
</script>
