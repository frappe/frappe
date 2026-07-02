// Composer.vue and ComposerHeader.vue stay private (the editing core / title bar).
// ComposerWindow is the shared window shell; compose it around EmailComposer or
// CommentComposer for a standalone single-channel window.
export { default as ComposerWindow } from "./ComposerWindow.vue";
export { default as EmailComposer } from "./EmailComposer/EmailComposer.vue";
export { default as CommentComposer } from "./CommentComposer/CommentComposer.vue";
export { default as MultiComposer } from "./MultiComposer.vue";
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
  MultiComposerProps,
  Recipient,
  RecipientSearch,
  Recipients,
  UploadedFile,
  UploadFunction,
} from "./types";
