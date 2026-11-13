<!-- `box` wraps a ghost control the way desk's FieldBox does. -->
<template>
	<div class="group/row grid grid-cols-[130px_1fr] items-start gap-2">
		<div class="flex h-7 min-w-0 items-center gap-1">
			<span class="truncate text-base text-ink-gray-5" :title="label">{{ label }}</span>
			<Tooltip v-if="lock" :text="lock">
				<span
					class="lucide-lock ml-auto size-3.5 shrink-0 text-ink-gray-4"
					:aria-label="__('Locked')"
					data-row-lock
				/>
			</Tooltip>
			<Tooltip v-else-if="changed" :text="resetText">
				<button
					type="button"
					class="group/reset ml-auto grid size-5 shrink-0 place-items-center rounded-3 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-8 focus-visible:bg-surface-gray-3"
					:aria-label="resetText"
					data-row-reset
					@click="$emit('reset')"
				>
					<span
						class="size-1.5 rounded-full bg-surface-gray-7 group-hover/row:hidden group-focus-visible/reset:hidden"
						data-row-changed
					/>
					<span
						class="lucide-rotate-ccw hidden size-3.5 group-hover/row:block group-focus-visible/reset:block"
						aria-hidden="true"
					/>
				</button>
			</Tooltip>
		</div>
		<div class="min-w-0" :class="{ 'opacity-60': lock }" :inert="Boolean(lock)">
			<div
				v-if="box"
				class="min-h-7 w-full min-w-0 rounded-4 focus-within:bg-surface-gray-2 focus-within:ring-1 focus-within:ring-inset focus-within:ring-outline-gray-3 hover:bg-surface-gray-2"
			>
				<slot />
			</div>
			<slot v-else />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui";
import { __ } from "@/i18n";

withDefaults(
	defineProps<{
		label: string;
		box?: boolean;
		lock?: string;
		changed?: boolean;
		resetText?: string;
	}>(),
	{ box: true, lock: "", resetText: "" }
);
defineEmits<{ reset: [] }>();
</script>
