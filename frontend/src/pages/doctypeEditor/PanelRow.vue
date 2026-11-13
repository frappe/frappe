<!-- A label-left row of the field panel, as frappe/crm#3419's PanelRow. `box` wraps a ghost control
     the way desk's FieldBox does. In Customize the label ends in a lock (the control goes inert) or
     a changed dot, which turns into a reset arrow while the row is hovered. -->
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
			<template v-else-if="changed">
				<span
					class="ml-auto grid size-5 shrink-0 place-items-center group-hover/row:hidden"
					:aria-label="__('Changed on this site')"
					data-row-changed
				>
					<span class="size-1.5 rounded-full bg-surface-gray-7" />
				</span>
				<Tooltip :text="resetText">
					<button
						type="button"
						class="ml-auto hidden size-5 shrink-0 place-items-center rounded-3 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-8 group-hover/row:grid"
						:aria-label="resetText"
						data-row-reset
						@click="$emit('reset')"
					>
						<span class="lucide-rotate-ccw size-3.5" aria-hidden="true" />
					</button>
				</Tooltip>
			</template>
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
