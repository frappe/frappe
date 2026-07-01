<template>
	<!-- icon ladder (first match wins): activity.icon (component > lucide string) > per-type default -->
	<component
		v-if="activity.icon && typeof activity.icon !== 'string'"
		:is="activity.icon"
		class="size-4 text-ink-gray-5"
	/>
	<span
		v-else-if="typeof activity.icon === 'string'"
		:class="[LUCIDE_ICON_CLASS[activity.icon], 'size-4 text-ink-gray-5']"
	/>
	<template v-else>
		<!-- email + comment: author avatar on the axis + channel badge (mail/comment) -->
		<div v-if="activity.type === 'email' || activity.type === 'comment'" class="relative">
			<Avatar size="lg" :label="activity.author.fullname" :image="activity.author.image" />
			<span
				class="absolute -bottom-0.5 -end-1.5 flex size-4.5 items-center justify-center rounded-full bg-surface-white text-ink-gray-5"
			>
				<MailIcon v-if="activity.type === 'email'" class="size-3" />
				<CommentIcon v-else class="size-3" />
			</span>
		</div>
		<template
			v-else-if="
				activity.type === 'log' ||
				activity.type === 'attachment_log' ||
				activity.type === 'version'
			"
		>
			<DotIcon
				v-if="
					activity.type === 'version' ||
					(activity.type === 'log' &&
						(activity.data.subtype === 'assigned' ||
							activity.data.subtype === 'assignment_completed' ||
							activity.data.subtype === 'created'))
				"
				class="text-ink-gray-3"
			/>
			<span v-else :class="[gutterIconClass(activity), 'size-4 text-ink-gray-5']" />
		</template>
		<CommentIcon v-else class="absolute start-[7.5px] text-ink-gray-5" />
	</template>
</template>

<script setup lang="ts">
import { Avatar } from "frappe-ui";
import MailIcon from "~icons/lucide/mail";
import { CommentIcon, DotIcon, SUBTYPE_ICON, LUCIDE_ICON_CLASS } from "./icons";
import type { Activity, AttachmentLogActivity, CustomActivity, LogActivity } from "./types";

defineProps<{
	activity: Activity | CustomActivity;
}>();

// literal lucide-* class for a log / attachment_log gutter dot (log icon derived
// from subtype; attachment from its add/remove action)
function gutterIconClass(activity: LogActivity | AttachmentLogActivity): string {
	const name =
		activity.type === "attachment_log"
			? activity.data.action === "removed"
				? "trash-2"
				: "paperclip"
			: SUBTYPE_ICON[activity.data.subtype] ?? "";
	return LUCIDE_ICON_CLASS[name] ?? "";
}
</script>
