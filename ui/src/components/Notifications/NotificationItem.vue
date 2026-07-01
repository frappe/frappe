<script setup lang="ts">
import { computed } from "vue";
import { Avatar, dayjs } from "frappe-ui";
import type { NotificationLog } from "./types";

const props = defineProps<{
	notification: NotificationLog;
	class?: string;
}>();

const emit = defineEmits<{
	click: [n: NotificationLog];
}>();

const avatarLabel = computed(() =>
	(props.notification.from_user || props.notification.type || "?").charAt(0)
);

// title/description are HTML rendered via v-html. The backend sanitizes this content at write
// time, so the UI does not re-sanitize here.
const title = computed(() => props.notification.title ?? props.notification.subject ?? "");
const description = computed(() => props.notification.description ?? "");

const isUnread = computed(() => !props.notification.read);
const timeAgo = computed(() => dayjs(props.notification.creation as string).fromNow());

function activate() {
	emit("click", props.notification);
}
</script>

<template>
	<!-- keyboard-operable row (P12): role + tabindex + Enter/Space, focus ring on keyboard focus -->
	<div
		role="button"
		tabindex="0"
		data-slot="item"
		:data-state="isUnread ? 'unread' : 'read'"
		class="flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-surface-gray-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
		:class="[isUnread ? 'bg-surface-gray-1/40' : '', props.class]"
		@click="activate"
		@keydown.enter.prevent="activate"
		@keydown.space.prevent="activate"
	>
		<div class="relative mt-0.5 flex-shrink-0">
			<span
				v-if="isUnread"
				class="absolute top-1/2 size-[5px] -translate-y-1/2 rounded-full bg-gray-800"
				style="left: -10px"
			>
				<span class="sr-only">Unread</span>
			</span>
			<slot name="prefix" :notification="notification">
				<Avatar :image="notification.from_user_image" :label="avatarLabel" size="lg" />
			</slot>
		</div>

		<div class="min-w-0 flex-1">
			<slot :notification="notification">
				<div class="text-p-base text-ink-gray-8 [&_b]:font-semibold" v-html="title" />
			</slot>
			<slot name="description" :notification="notification">
				<div
					v-if="description"
					class="mt-1 text-p-sm text-ink-gray-5 line-clamp-2"
					v-html="description"
				/>
			</slot>
			<slot name="suffix" :notification="notification">
				<div class="mt-1 text-p-xs text-ink-gray-5">{{ timeAgo }}</div>
			</slot>
		</div>
	</div>
</template>
