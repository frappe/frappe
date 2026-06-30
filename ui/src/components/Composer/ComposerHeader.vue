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
			<Tooltip v-if="expandable" :text="floating ? 'Minimise' : 'Expand'" :hover-delay="0">
				<Button variant="ghost" @click="emit('expand')">
					<template #icon>
						<LucideMinimize2 v-if="floating" class="h-4 w-4 text-ink-gray-5" />
						<LucideExpand v-else class="h-4 w-4 text-ink-gray-5" />
					</template>
				</Button>
			</Tooltip>
			<Tooltip v-if="minimizable" text="Save and close" :hover-delay="0">
				<Button variant="ghost" @click="emit('minimize')">
					<template #icon>
						<LucideX class="h-4 w-4 text-ink-gray-5" />
					</template>
				</Button>
			</Tooltip>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, Tooltip } from "frappe-ui";
import LucideX from "~icons/lucide/x";
import LucideExpand from "~icons/lucide/maximize-2";
import LucideMinimize2 from "~icons/lucide/minimize-2";

withDefaults(
	defineProps<{
		title: string;
		expandable?: boolean;
		floating?: boolean;
		minimizable?: boolean;
		minimized?: boolean;
	}>(),
	{ expandable: false, minimizable: false }
);

const emit = defineEmits<{ expand: []; minimize: [] }>();
</script>
