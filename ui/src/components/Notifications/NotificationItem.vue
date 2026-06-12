<script setup lang="ts">
import { computed } from "vue";
import type { Component } from "vue";
import { Avatar, FeatherIcon, dayjs } from "frappe-ui";
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

// string => render via frappe-ui's icon component; Component => render directly;
// undefined => fall back to the sender's Avatar (the common case).
const iconName = computed(() => (typeof props.icon === "string" ? props.icon : undefined));
const iconComponent = computed(() =>
	props.icon && typeof props.icon !== "string" ? (props.icon as Component) : undefined
);

// fallback initials for the Avatar when there is no sender image
const avatarLabel = computed(() =>
	(props.notification.from_user || props.notification.type || "?").charAt(0)
);

const title = computed(() => props.notification.title ?? props.notification.subject ?? "");
const description = computed(() => props.notification.description ?? "");

const isUnread = computed(() => !props.notification.read);
const timeAgo = computed(() => dayjs(props.notification.creation as string).fromNow());
</script>

<template>
	<div
		class="flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-surface-gray-1"
		:class="[isUnread ? 'bg-surface-gray-1/40' : '', props.class]"
		@click="emit('click', notification)"
	>
		<!-- leading visual: avatar/icon, left edge aligned with the header + tabs (px-4 = the
		     panel's content margin). The unread dot is absolutely placed in the left padding, so
		     it stays outside the aligned avatar/text column and never shifts the avatar. -->
		<div class="relative mt-0.5 flex-shrink-0">
			<!-- layout via Tailwind (hardcoded values); only the gray-800 color is inline,
			     since frappe-ui's preset drops the default `gray-*` utilities -->
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

		<!-- body -->
		<div class="min-w-0 flex-1">
			<!-- text-p-* are frappe-ui's paragraph sizes; they carry the design system's
			     comfortable line-heights (1.5–1.6) instead of the tight 1.15 of plain text-*. -->
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
