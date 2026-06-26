<template>
  <!--
		Email owns its window: the composer wraps itself in a FloatingWindow so the
		title, field toggles, and the float/dock control share one bar that doubles
		as the window's title bar and drag handle. `v-model:mode` lets a host
		observe or drive docked / floating / minimized.
	-->
  <FloatingWindow
    v-model:mode="windowMode"
    :storage-key="storageKey ? `${storageKey}:window` : null"
    :minimizable="false"
  >
    <template #header="{ mode, float, dock }">
      <ComposerHeader
        class="px-2.5"
        :title="channelLabel"
        :expandable="expandable"
        :floating="mode !== 'docked'"
        @expand="mode === 'docked' ? float() : dock()"
      >
        <!-- Channel switcher: turns the title into an Email/Comment dropdown. -->
        <template v-if="switchable" #title>
          <div class="flex gap-[4px] items-center">
            <span class="text-ink-gray-5 text-base">Via</span>
            <Dropdown :options="channelOptions" placement="bottom-start">
              <button
                class="flex items-center gap-1 rounded px-1.5 py-0.5 text-base text-ink-gray-7 hover:bg-surface-gray-2"
              >
                {{ channelLabel }}
                <FeatherIcon
                  name="chevron-down"
                  class="h-4 w-4 text-ink-gray-5"
                />
              </button>
            </Dropdown>
          </div>
        </template>

        <!-- Cc/Bcc toggles only apply to email; hidden in comment mode. -->
        <template v-if="channel === 'email'" #actions>
          <!-- Reveal the optional Cc/Bcc recipient rows. Which toggles appear
					 is set by `fields`; To/Subject are prop-driven, not toggled. -->
          <Button
            v-if="fields?.includes('cc')"
            variant="ghost"
            label="CC"
            :class="showCc ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
            @click="showCc = !showCc"
          />
          <Button
            v-if="fields?.includes('bcc')"
            variant="ghost"
            label="BCC"
            :class="showBcc ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
            @click="showBcc = !showBcc"
          />
        </template>
      </ComposerHeader>
    </template>

    <Composer
      ref="composer"
      :storage-key="storageKey"
      :placeholder="placeholder"
      :label="submitLabel"
      :upload-function="uploadFunction"
      :signature="channel === 'comment' ? undefined : signature"
      :mentions="mentions"
      v-model:body="body"
      :on-submit="handleSubmit"
      @discard="emit('discard')"
      @submitted="resetFields"
      @remove-attachment="emit('remove-attachment', $event)"
    >
      <template #top>
        <!-- Email-only: the host's From picker and the recipient rows.
					 Comment mode is just the editing core, so they're hidden. -->
        <template v-if="channel === 'email'">
          <slot name="from" />
          <RecipientFields
            v-model="recipients"
            v-model:subject="subject"
            :show-subject="showSubject"
            :show-cc="showCc"
            :show-bcc="showBcc"
            :search="searchRecipients"
          />
        </template>
      </template>

      <!-- Attachments, canned-response pickers, etc. are host-supplied: wire a
				 FileUploader to `addAttachment` and report progress via `setUploading`. -->
      <template v-if="$slots.utilities" #utilities="utilityProps">
        <slot name="utilities" v-bind="utilityProps" />
      </template>
    </Composer>
  </FloatingWindow>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import {
  Button,
  Dropdown,
  FeatherIcon,
  FloatingWindow,
  toast,
  type WindowMode,
} from "frappe-ui";
import Composer from "../Composer.vue";
import ComposerHeader from "../ComposerHeader.vue";
import RecipientFields from "./RecipientFields.vue";
import type {
  Channel,
  CoreSubmitPayload,
  EmailComposerProps,
  Recipients,
  UploadedFile,
} from "../types";

const props = withDefaults(defineProps<EmailComposerProps>(), {
  fields: () => ["cc", "bcc"],
  expandable: true,
  switchable: false,
});

const emit = defineEmits<{
  discard: [];
  "remove-attachment": [file: UploadedFile];
}>();

// The window state, host-observable via `v-model:mode`. The composer owns its
// own FloatingWindow now, so the float/dock control lives in its header.
const windowMode = defineModel<WindowMode>("mode", { default: "docked" });

// The active channel, host-observable via `v-model:channel`. Only switchable
// when `switchable` is on; otherwise it stays "email".
const channel = defineModel<Channel>("channel", { default: "email" });
const channelLabel = computed(() =>
  channel.value === "comment" ? "Comment" : "Email"
);
const submitLabel = computed(() =>
  channel.value === "comment" ? "Comment" : props.label
);
const channelOptions = [
  { label: "Email", onClick: () => (channel.value = "email") },
  { label: "Comment", onClick: () => (channel.value = "comment") },
];

// Two-way state, host-owned. Seed and observe via v-models; defaults make them
// optional. (Attachments stay owned by the base — see `remove-attachment`.)
const body = defineModel<string>("body", { default: "" });
const recipients = defineModel<Recipients>("recipients", {
  default: () => ({ to: [], cc: [], bcc: [] }),
});
const subject = defineModel<string>("subject", { default: "" });

const composer = ref<InstanceType<typeof Composer> | null>(null);

// To is always shown; Subject shows whenever `fields` includes it.
// Cc/Bcc stay hidden until revealed from the header (or a prefilled value opens them).
const showSubject = computed(() => props.fields?.includes("subject") ?? false);
const showCc = ref(false);
const showBcc = ref(false);

function hasRecipients() {
  const { to, cc, bcc } = recipients.value;
  return Boolean(to.length || cc.length || bcc.length);
}

// The base hands us the body + attachments; we guard recipients, add the email
// envelope, and pass it on. Throwing aborts the submit and keeps the draft.
async function handleSubmit({ body: message, attachments }: CoreSubmitPayload) {
  // Comment mode carries no recipients — hand the body straight to onComment.
  if (channel.value === "comment") {
    await props.onComment?.({ body: message, attachments });
    return;
  }
  if (!hasRecipients()) {
    toast.warning("Add at least one recipient before sending.");
    throw new Error("EmailComposer: no recipients");
  }
  await props.onSubmit?.({
    subject: subject.value,
    body: message,
    recipients: recipients.value,
    attachments,
  });
}

function resetFields() {
  recipients.value = { to: [], cc: [], bcc: [] };
  subject.value = "";
}

function reset() {
  resetFields();
  composer.value?.reset();
}

const editor = computed(() => composer.value?.editor);

defineExpose({
  editor,
  focus: () => composer.value?.focus(),
  reset,
  submit: () => composer.value?.submit(),
  // Drop a quoted message into the collapsible reply block. To pre-fill a
  // reply, set `v-model:recipients` and call this.
  setQuotedReply: (content: string) => composer.value?.setQuotedReply(content),
});
</script>
