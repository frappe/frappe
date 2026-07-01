<template>
	<!-- Wraps EmailComposer + CommentComposer in one ComposerWindow with a channel
		 switcher in the header; owns no composing logic, just routes events out. -->
	<ComposerWindow
		ref="windowRef"
		v-model:mode="mode"
		:title="channelLabel"
		:expandable="expandable"
		:avatar="avatar"
		:avatar-label="avatarLabel"
		:placeholder="placeholder"
	>
		<template #title>
			<TabButtons v-model="channel" :options="channelOptions" />
		</template>

		<EmailComposer
			v-if="channel === 'email'"
			ref="content"
			:placeholder="placeholder"
			:label="label"
			:upload-function="uploadFunction"
			:fields="fields"
			:search-recipients="searchRecipients"
			:on-submit="handleSubmit"
			v-model:body="body"
			v-model:quoted="quotedReply"
			v-model:recipients="recipients"
			v-model:subject="subject"
			@discard="handleDiscard"
			@remove-attachment="emit('remove-attachment', $event)"
		>
			<template v-if="$slots.from" #from><slot name="from" /></template>
			<template v-if="$slots.actions" #actions="actionProps">
				<slot name="actions" v-bind="actionProps" />
			</template>
		</EmailComposer>

		<!-- `commentBody` lives here (not in CommentComposer) so it survives an
			 unmount on collapse / channel switch, kept separate from the email body. -->
		<CommentComposer
			v-else
			ref="content"
			:placeholder="placeholder"
			:upload-function="uploadFunction"
			:mention-options="mentionOptions"
			:on-submit="handleSubmitComment"
			v-model:body="commentBody"
			@discard="handleDiscard"
			@remove-attachment="emit('remove-attachment', $event)"
		>
			<template v-if="$slots.actions" #actions="actionProps">
				<slot name="actions" v-bind="actionProps" />
			</template>
		</CommentComposer>
	</ComposerWindow>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { TabButtons } from "frappe-ui";
import { type WindowMode } from "frappe-ui/experimental";
import ComposerWindow from "./ComposerWindow.vue";
import EmailComposer from "./EmailComposer/EmailComposer.vue";
import CommentComposer from "./CommentComposer/CommentComposer.vue";
import type {
	Channel,
	CommentPayload,
	EmailPayload,
	MultiComposerProps,
	Recipients,
	UploadedFile,
} from "./types";

const props = withDefaults(defineProps<MultiComposerProps>(), {
	fields: () => ["cc", "bcc"],
	expandable: true,
});

const emit = defineEmits<{
	discard: [];
	"remove-attachment": [file: UploadedFile];
}>();

// Window + channel state, host-observable via v-models.
const mode = defineModel<WindowMode>("mode", { default: "docked" });
const channel = defineModel<Channel>("channel", { default: "email" });

// Email channel state (host-observable). Comment draft and quoted reply are
// kept in local refs, not v-modelled, so they survive collapse/channel switch
// without leaking across channels.
const body = defineModel<string>("body", { default: "" });
const recipients = defineModel<Recipients>("recipients", {
	default: () => ({ to: [], cc: [], bcc: [] }),
});
const subject = defineModel<string>("subject", { default: "" });
const commentBody = ref("");
const quotedReply = ref<string | null>(null);

const channelLabel = computed(() => (channel.value === "comment" ? "Comment" : "Email"));
const channelOptions = [
	{ label: "Email", value: "email" },
	{ label: "Comment", value: "comment" },
];

const windowRef = ref<InstanceType<typeof ComposerWindow> | null>(null);
const content = ref<
	InstanceType<typeof EmailComposer> | InstanceType<typeof CommentComposer> | null
>(null);

function handleDiscard() {
	windowRef.value?.collapse();
	emit("discard");
}

// Collapse once the send resolves. Only reached on success — a host that
// wants to keep the draft on failure must reject `onSubmit`/`onSubmitComment`
// (per the documented contract), not swallow its own error and resolve.
async function handleSubmit(payload: EmailPayload) {
	await props.onSubmit(payload);
	windowRef.value?.collapse();
}

async function handleSubmitComment(payload: CommentPayload) {
	await props.onSubmitComment(payload);
	windowRef.value?.collapse();
}

// Open the window, then focus the freshly-mounted channel component.
async function expand() {
	await windowRef.value?.expand();
	content.value?.focus();
}

defineExpose({
	editor: computed(() => content.value?.editor),
	expand,
	collapse: () => windowRef.value?.collapse(),
	focus: () => content.value?.focus(),
	reset: () => content.value?.reset(),
	submit: () => content.value?.submit(),
	// Email-only; a no-op while the comment channel is active. `channel` (not
	// duck-typing `content.value`) is the actual discriminant for which
	// component is mounted.
	setQuotedReply: (quoted: string) => {
		if (channel.value === "email") {
			(content.value as InstanceType<typeof EmailComposer> | null)?.setQuotedReply(quoted);
		}
	},
});
</script>
