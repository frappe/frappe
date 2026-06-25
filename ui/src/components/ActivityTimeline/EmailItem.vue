<template>
	<div
		class="grow cursor-pointer overflow-hidden rounded-md border border-outline-gray-2 bg-surface-white text-base leading-6 transition-all duration-300 ease-in-out"
	>
		<div class="px-3 pb-2 pt-2">
			<slot name="header" :email="email">
				<div class="flex items-center justify-between gap-2">
					<div class="flex items-center gap-1">
						<span>{{ email.author.fullname || "Guest" }}</span>
						<span
							v-if="email.data.sender"
							class="hidden text-sm text-ink-gray-5 sm:flex"
						>
							{{ "<" + email.data.sender + ">" }}
						</span>
					</div>
					<div class="flex items-center gap-2">
						<Badge
							v-if="status.label"
							:label="status.label"
							variant="subtle"
							:theme="status.color"
						/>
						<Tooltip :text="dateFormat(email.timestamp)">
							<p class="text-xs text-ink-gray-5 md:text-sm">
								{{ timeAgo(email.timestamp) }}
							</p>
						</Tooltip>
						<div v-if="$slots.actions" class="flex items-center gap-1">
							<slot name="actions" />
						</div>
					</div>
				</div>
				<div class="text-p-sm text-ink-gray-5">
					<template
						v-for="(val, label) in {
							To: email.data.to,
							cc: email.data.cc,
							bcc: email.data.bcc,
						}"
						:key="label"
					>
						<span v-if="val" class="me-1.5">
							<span class="me-1 text-ink-gray-7">{{ label }}:</span>
							<span>{{ splitRecipients(val).join(", ") }}</span>
						</span>
					</template>
				</div>
			</slot>
		</div>
		<hr class="border-t border-outline-gray-modals" />
		<!-- body region owns its own horizontal padding -->
		<div class="px-3 pb-2 pt-3">
			<EmailContent :content="email.data.content" />
			<slot name="footer" :email="email">
				<div v-if="email.data.attachments.length" class="mt-2 flex flex-wrap gap-2">
					<AttachmentItem
						v-for="a in email.data.attachments"
						:key="a.file_url"
						:label="a.file_name"
						:url="a.file_url"
					/>
				</div>
			</slot>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Tooltip } from "frappe-ui";
import { computed } from "vue";
import AttachmentItem from "./AttachmentItem.vue";
import EmailContent from "./EmailContent.vue";
import type { EmailActivity } from "./types";
import { dateFormat, splitRecipients, timeAgo } from "./utils";

const props = defineProps<{
	email: EmailActivity;
}>();

const status = computed(() => {
	const _status = props.email.data.deliveryStatus;
	let color = "red";
	if (["Sent", "Clicked"].includes(_status)) color = "green";
	else if (["Sending", "Scheduled"].includes(_status)) color = "orange";
	else if (["Opened", "Read"].includes(_status)) color = "blue";
	return { label: _status, color };
});
</script>
