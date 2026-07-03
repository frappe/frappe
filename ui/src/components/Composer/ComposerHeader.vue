<template>
	<!-- Title bar for FloatingWindow's `#header` slot (also the drag handle): title
		 on the left, window controls on the right. We render our own controls so a
		 host can hide them with `floatable=false`. -->
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
			<!-- Window controls (expand / minimize), exposed as an overridable slot.

				 The default content below is the standard button pair. A consumer can
				 replace it entirely by filling this slot; the slot props hand back the
				 `expand` and `minimize` actions plus the current `floating` state, so
				 custom controls still drive the real window behavior instead of having
				 to re-implement it. `expand` / `minimize` are wrapped as callables so
				 the slot can invoke them directly (e.g. `@click="expand"`). -->
			<slot
				name="actions"
				:expand="() => emit('expand')"
				:minimize="() => emit('minimize')"
				:floating="floating"
			>
				<Tooltip
					v-if="floatable"
					:text="floating ? 'Minimise' : 'Expand'"
					:hover-delay="0"
				>
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
			</slot>
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
		floatable?: boolean;
		floating?: boolean;
		minimizable?: boolean;
		minimized?: boolean;
	}>(),
	{ floatable: false, minimizable: false }
);

const emit = defineEmits<{ expand: []; minimize: [] }>();
</script>
