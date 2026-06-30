<template>
	<!-- Title bar for FloatingWindow's `#header` slot (also the drag handle): title
		 on the left, `#actions` (Cc/Bcc toggles) and window controls on the right.
		 We render our own controls so a host can hide them with `expandable=false`. -->
	<div class="flex items-center justify-between gap-2 py-1.5">
		<!-- Title, or a host-supplied trigger (e.g. the channel switcher). Minimized
			 drops the trigger for the plain label, truncated to fit the tray strip. -->
		<span v-if="minimized" class="min-w-0 truncate text-p-sm text-ink-gray-8">
			{{ title }}
		</span>
		<slot v-else name="title">
			<span class="font-medium text-ink-gray-8">{{ title }}</span>
		</slot>

		<div class="flex shrink-0 items-center gap-1">
			<slot name="actions" />
			<Button v-if="minimizable" variant="ghost" @click="emit('minimize')">
				<template #icon>
					<FeatherIcon
						:name="minimized ? 'maximize-2' : 'minus'"
						class="h-4 w-4 text-ink-gray-5"
					/>
				</template>
			</Button>
			<Button v-if="expandable" variant="ghost" @click="emit('expand')">
				<template #icon>
					<!-- Floating: close (dock back). Docked: pop out. -->
					<FeatherIcon v-if="floating" name="x" class="h-4 w-4 text-ink-gray-5" />
					<LucideSquareArrowOutUpRight v-else class="h-4 w-4 text-ink-gray-5" />
				</template>
			</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, FeatherIcon } from "frappe-ui";
import LucideSquareArrowOutUpRight from "~icons/lucide/square-arrow-out-up-right";

withDefaults(
	defineProps<{
		/** Channel label shown on the left (e.g. "Email"). */
		title: string;
		/** Show the pop-out/close control (emits `expand`). Off by default. */
		expandable?: boolean;
		/** Host window detached — swaps the control's icon. */
		floating?: boolean;
		/** Show the minimize control (emits `minimize`). Off by default. */
		minimizable?: boolean;
		/** Host window minimized — swaps the control's icon. */
		minimized?: boolean;
	}>(),
	{ expandable: false, minimizable: false }
);

const emit = defineEmits<{ expand: []; minimize: [] }>();
</script>
