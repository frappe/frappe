<script setup lang="ts">
import { computed } from "vue";
import type { Component } from "vue";
import { Avatar, FeatherIcon, dayjs } from "frappe-ui";
import { sanitizeHtml } from "../../utils/sanitize";
import type { NotificationIcon, NotificationLog } from "./types";

const props = defineProps<{
	notification: NotificationLog;
	/** lucide/feather icon name (string) or a Component; omitted => sender avatar */
	icon?: NotificationIcon;
	class?: string;
}>();

const emit = defineEmits<{
	click: [n: NotificationLog];
}>();

const iconName = computed(() => (typeof props.icon === "string" ? props.icon : undefined));
const iconComponent = computed(() =>
	props.icon && typeof props.icon !== "string" ? (props.icon as Component) : undefined
);

const avatarLabel = computed(() =>
	(props.notification.from_user || props.notification.type || "?").charAt(0)
);

// title/description are rendered HTML bound via v-html; sanitize to neutralize any
// user-controlled markup injected through Jinja document-field values (stored XSS).
const title = computed(() =>
	sanitizeHtml(props.notification.title ?? props.notification.subject ?? "")
);
const description = computed(() => sanitizeHtml(props.notification.description ?? ""));

const isUnread = computed(() => !props.notification.read);
const timeAgo = computed(() => dayjs(props.notification.creation as string).fromNow());
</script>

<template>
	<div
		class="flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-surface-gray-1"
		:class="[isUnread ? 'bg-surface-gray-1/40' : '', props.class]"
		@click="emit('click', notification)"
	>
		<div class="relative mt-0.5 flex-shrink-0">
			<span
				v-if="isUnread"
				class="absolute top-1/2 size-[5px] -translate-y-1/2 rounded-full bg-gray-800"
				style="left: -10px"
			/>
			<component :is="iconComponent" v-if="iconComponent" :notification="notification" />
			<div
				v-else-if="iconName"
				class="flex size-8 items-center justify-center rounded-full bg-surface-gray-3 text-ink-gray-7"
			>
				<FeatherIcon :name="iconName" class="size-4" />
			</div>
			<Avatar v-else :image="notification.from_user_image" :label="avatarLabel" size="lg" />
		</div>

		<div class="min-w-0 flex-1">
			<div class="text-p-base text-ink-gray-8 [&_b]:font-semibold" v-html="title" />
			<div
				v-if="description"
				class="mt-1 text-p-sm text-ink-gray-5 line-clamp-2"
				v-html="description"
			/>
			<div class="mt-1 text-p-xs text-ink-gray-5">{{ timeAgo }}</div>
		</div>
	</div>
</template>
