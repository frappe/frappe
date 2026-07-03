// Public surface of the Composer.
//
// The component is built as a set of compound parts that share state through
// an injected context rather than through props drilled down a single monolith
// — assemble only the parts a given surface needs:
//
//   Composer         Root. Owns the shared state (open, active channel, window
//                    mode) and provides it to every part below via context.
//   ComposerTrigger  The collapsed bar shown while the window is closed; click
//                    to open.
//   ComposerContent  The window itself (floating/docked/minimized chrome).
//   ComposerChannel  Associates slotted content with a channel value, and
//                    contributes a switcher tab when more than one is present.
//
// EmailComposer / CommentComposer are ready-made channel *content*. They render
// inline and standalone (no window) when used on their own, or become a channel
// when wrapped in a ComposerChannel inside a Composer.
//
// ComposerEditor.vue and ComposerHeader.vue are intentionally NOT exported:
// they are internal building blocks (the editing core and the window title
// bar) that the parts above compose.
export { default as Composer } from "./Composer.vue";
export { default as ComposerTrigger } from "./ComposerTrigger.vue";
export { default as ComposerContent } from "./ComposerContent.vue";
export { default as ComposerChannel } from "./ComposerChannel.vue";
export { default as EmailComposer } from "./EmailComposer/EmailComposer.vue";
export { default as CommentComposer } from "./CommentComposer/CommentComposer.vue";
// For custom channel content: hand a draft preview + focus to the window.
export { useComposerSurface } from "./composerContext";
export type { ChannelSurface } from "./composerContext";
// Re-export so consumers can type `v-model:mode` without reaching into frappe-ui.
export type { WindowMode } from "frappe-ui/experimental";
export type {
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
