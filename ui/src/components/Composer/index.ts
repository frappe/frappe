// Composer.vue and ComposerHeader.vue stay private (the editing core).
export { default as EmailComposer } from "./EmailComposer/EmailComposer.vue";
export { default as CommentComposer } from "./CommentComposer/CommentComposer.vue";
// Re-export so consumers can type `v-model:mode` without reaching into frappe-ui.
export type { WindowMode } from "frappe-ui/experimental";
export type {
  Channel,
  CommentComposerProps,
  CommentPayload,
  EmailComposerProps,
  EmailPayload,
  Field,
  MentionOption,
  Recipient,
  RecipientSearch,
  Recipients,
  UploadedFile,
  UploadFunction,
} from "./types";
