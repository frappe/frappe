<template>
	<TimelineCard content-class="px-3 pb-2">
		<template #header>
			<div class="ps-3" :class="$slots.actions ? 'pe-1.5' : 'pe-3'">
				<slot name="header" :email="email">
					<!-- 40px header; its center aligns with the gutter avatar -->
					<div class="flex h-10 items-center justify-between gap-2">
						<!-- sender email is hidden; surfaced on hover via tooltip -->
						<Tooltip :text="email.data.sender">
							<span class="text-base font-medium text-ink-gray-6">{{
								email?.author?.fullname || "Guest"
							}}</span>
						</Tooltip>
						<div class="flex items-center gap-2">
							<Badge
								v-if="status.label"
								:label="status.label"
								variant="subtle"
								:theme="status.color"
							/>
							<TimeAgo :timestamp="email.timestamp" class="text-sm" />
							<div v-if="$slots.actions" class="flex items-center gap-1">
								<slot name="actions" />
							</div>
						</div>
					</div>
					<div
						v-if="email.data.to || email.data.cc || email.data.bcc"
						class="pb-2 text-p-sm text-ink-gray-5"
					>
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
		</template>

		<!-- content: no top padding so the iframe sits flush to the <hr> and clips at the border -->
		<EmailContent :content="email.data.content" />
		<slot name="footer" :email="email">
			<div v-if="email.data?.attachments?.length" class="mt-2 flex flex-wrap gap-2">
				<Attachment
					v-for="a in email.data.attachments"
					:key="a.file_url"
					:label="a.file_name"
					:url="a.file_url"
				/>
			</div>
		</slot>
	</TimelineCard>
</template>

<script setup lang="ts">
import { Badge, Tooltip } from "frappe-ui";
import { computed } from "vue";
import Attachment from "./Attachment.vue";
import EmailContent from "./EmailContent.vue";
import TimeAgo from "./TimeAgo.vue";
import TimelineCard from "./TimelineCard.vue";
import type { EmailActivity } from "./types";
import { splitRecipients } from "./utils";

const props = defineProps<{
	email: EmailActivity;
}>();

const status = computed(() => {
	const deliveryStatus = props.email.data.deliveryStatus ?? "";
	let color = "red";
	if (["Sent", "Clicked"].includes(deliveryStatus)) color = "green";
	else if (["Sending", "Scheduled"].includes(deliveryStatus)) color = "orange";
	else if (["Opened", "Read"].includes(deliveryStatus)) color = "blue";
	return { label: deliveryStatus, color };
});
</script>
