<template>
	<div
		class="grow cursor-pointer rounded-md border border-outline-gray-2 bg-surface-white text-base leading-6 transition-all duration-300 ease-in-out"
	>
		<!-- header / body / footer slots: override a single region, or leave it to
		     the default markup. Surfaced through ActivityTimeline as
		     #item-email-{header,body,footer}. -->
		<slot name="header" :email="email">
			<div class="flex items-center justify-between gap-2">
				<div class="flex items-center gap-1">
					<span>{{ email.author.fullname || "Guest" }}</span>
					<span v-if="email.data.sender" class="hidden text-sm text-ink-gray-5 sm:flex">
						{{ "<" + email.data.sender + ">" }}
					</span>
				</div>
				<div class="flex items-center gap-2">
					<div class="flex items-center gap-0.5">
						<Badge
							v-if="status.label"
							:label="status.label"
							variant="subtle"
							:theme="status.color"
							class="me-1.5"
						/>
						<Tooltip :text="dateFormat(email.timestamp)">
							<p class="text-xs text-ink-gray-5 md:text-sm">
								{{ timeAgo(email.timestamp) }}
							</p>
						</Tooltip>
					</div>
					<div class="flex items-center gap-1">
						<Button tooltip="Reply" variant="ghost" @click="reply">
							<template #icon>
								<ReplyIcon class="text-ink-gray-7" />
							</template>
						</Button>
						<Button tooltip="Reply All" variant="ghost" @click="replyAll">
							<template #icon>
								<ReplyAllIcon class="text-ink-gray-7" />
							</template>
						</Button>
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
			<div class="border-0 border-t mb-3 border-outline-gray-modals !-mx-3 mt-2" />
		</slot>
		<slot name="body" :email="email">
			<EmailContent :content="email.data.content" :css-href="cssHref" />
		</slot>
		<slot name="footer" :email="email">
			<div v-if="email.data.attachments.length" class="flex flex-wrap gap-2">
				<AttachmentItem
					v-for="a in email.data.attachments"
					:key="a.file_url"
					:label="a.file_name"
					:url="a.file_url"
				/>
			</div>
		</slot>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, Tooltip } from "frappe-ui";
import { computed } from "vue";
import AttachmentItem from "./AttachmentItem.vue";
import EmailContent from "./EmailContent.vue";
import { ReplyAllIcon, ReplyIcon } from "./icons";
import type { EmailActivity } from "./types";
import { dateFormat, splitRecipients, timeAgo } from "./utils";

const props = withDefaults(
	defineProps<{
		email: EmailActivity;
		cssHref?: string;
		currentUser?: string;
	}>(),
	{
		currentUser: "",
	}
);

const emit = defineEmits(["reply"]);

const status = computed(() => {
	const _status = props.email.data.deliveryStatus;
	let color = "red";
	if (["Sent", "Clicked"].includes(_status)) {
		color = "green";
	} else if (["Sending", "Scheduled"].includes(_status)) {
		color = "orange";
	} else if (["Opened", "Read"].includes(_status)) {
		color = "blue";
	}
	return { label: _status, color };
});

const reply = () => {
	const user = props.currentUser;
	emit("reply", {
		content: props.email.data.content,
		to: user === props.email.data.sender ? props.email.data.to : props.email.data.sender,
	});
};

const replyAll = () => {
	const user = props.currentUser;
	const exclude = [user, props.email.data.sender];
	const filteredTo = splitRecipients(props.email.data.to, exclude);
	const filteredCc = splitRecipients(props.email.data.cc, exclude);
	const filteredBcc = splitRecipients(props.email.data.bcc, exclude);

	let _to: string;
	let _cc: string[];
	let _bcc: string[];

	if (user === props.email.data.sender) {
		// User is the sender, reply to all original recipients
		_to = filteredTo.join(", ");
		_cc = filteredCc;
		_bcc = filteredBcc;
	} else {
		// User is a recipient, reply to sender with all other recipients in cc
		_to = props.email.data.sender;
		_cc = [...filteredTo, ...filteredCc];
		_bcc = filteredBcc;
	}

	emit("reply", {
		content: props.email.data.content,
		to: _to,
		cc: _cc.filter(Boolean),
		bcc: _bcc.filter(Boolean),
	});
};
</script>
