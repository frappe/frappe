<template>
	<!--
		The email window's title bar, rendered into FloatingWindow's `#header`
		slot (which also serves as the drag handle while floating). It owns the
		whole row: the channel title on the left, then the channel-specific
		controls (the Cc/Bcc toggles, via `#actions`) and the window control on
		the right. We render our own window button rather than FloatingWindow's
		built-in one because a host can hide it with `expandable=false` for a
		fixed, docked-only composer — and because supplying `#header` replaces
		FloatingWindow's built-in chrome (title + `#actions`) entirely.
	-->
	<div class="flex items-center justify-between gap-2 py-1.5">
		<!-- Title, or a host-supplied trigger (e.g. EmailComposer's channel
			 dropdown) that replaces the plain label. While minimized the window is
			 just a tray strip, so drop the trigger and show the plain title (the
			 subject) instead, truncated to fit. -->
		<span
			v-if="minimized"
			class="min-w-0 truncate font-medium text-ink-gray-8"
		>
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
					<FeatherIcon
						:name="floating ? 'x' : 'maximize-2'"
						class="h-4 w-4 text-ink-gray-5"
					/>
				</template>
			</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, FeatherIcon } from "frappe-ui";

withDefaults(
	defineProps<{
		/** Channel label shown on the left (e.g. "Email"). */
		title: string;
		/** Show the window control (emits `expand`): pop-out vs. close-back.
		 *  Off by default — only a host that handles `expand` (EmailComposer)
		 *  opts in; CommentComposer renders the bare title. */
		expandable?: boolean;
		/** Whether the host window is detached, which swaps the control's icon. */
		floating?: boolean;
		/** Show the minimize control (emits `minimize`). Off by default. */
		minimizable?: boolean;
		/** Whether the host window is minimized, which swaps the control's icon. */
		minimized?: boolean;
	}>(),
	{ expandable: false, minimizable: false }
);

const emit = defineEmits<{ expand: []; minimize: [] }>();
</script>
