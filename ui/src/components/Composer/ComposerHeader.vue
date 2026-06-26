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
		<span class="font-medium text-ink-gray-8">{{ title }}</span>

		<div class="flex items-center gap-1">
			<slot name="actions" />
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
	}>(),
	{ expandable: false }
);

const emit = defineEmits<{ expand: [] }>();
</script>
