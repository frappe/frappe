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
			<component v-else :is="gutterIcon(activity)" class="size-4 text-ink-gray-5" />
		</template>
		<CommentIcon v-else class="absolute start-[7.5px] text-ink-gray-5" />
	</template>
</template>

<script setup lang="ts">
import type { Component } from "vue";
import { Avatar } from "frappe-ui";
import MailIcon from "~icons/lucide/mail";
import LucideHeart from "~icons/lucide/heart";
import LucideGitBranch from "~icons/lucide/git-branch";
import LucideInfo from "~icons/lucide/info";
import LucideEye from "~icons/lucide/eye";
import LucidePaperclip from "~icons/lucide/paperclip";
import LucideTrash2 from "~icons/lucide/trash-2";
import { CommentIcon, DotIcon, LUCIDE_ICON_CLASS } from "./icons";
import type { Activity, AttachmentLogActivity, CustomActivity, LogActivity } from "./types";

defineProps<{
	activity: Activity | CustomActivity;
}>();

// Built-in gutter icons per log subtype, inlined as SVG components (unplugin-icons,
// like MailIcon above) so they render without a host emitting the lucide-* mask class.
const LOG_SUBTYPE_ICON: Record<string, Component> = {
	like: LucideHeart,
	workflow: LucideGitBranch,
	info: LucideInfo,
	view: LucideEye,
};

// The gutter icon component for a log / attachment_log row (attachment from its
// add/remove action; log from its subtype). Undefined for subtypes with no icon.
function gutterIcon(activity: LogActivity | AttachmentLogActivity): Component | undefined {
	if (activity.type === "attachment_log")
		return activity.data.action === "removed" ? LucideTrash2 : LucidePaperclip;
	return LOG_SUBTYPE_ICON[activity.data.subtype];
}
</script>
