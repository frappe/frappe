// Composer.vue and ComposerHeader.vue are intentionally NOT exported: they are the
// private editing core. Consumers pick a channel (EmailComposer / CommentComposer);
// a new channel means a new thin wrapper, never importing the base directly.
export { default as EmailComposer } from "./EmailComposer/EmailComposer.vue";
export { default as CommentComposer } from "./CommentComposer/CommentComposer.vue";
// MultiComposer is an EmailComposer that flips between Email and Comment from a
// header dropdown (it owns its own FloatingWindow, like EmailComposer).
export { default as MultiComposer } from "./MultiComposer/MultiComposer.vue";
// EmailComposer / MultiComposer own a FloatingWindow; re-export its mode type so
// a consumer can type `v-model:mode` without reaching into frappe-ui internals.
export type { WindowMode } from "frappe-ui";
// ComposerProps, CoreSubmitPayload, and CoreSubmitHandler are the private core's
// contract and stay internal alongside Composer.vue. The channel aliases below
// (CommentComposerProps = ComposerProps, CommentPayload = CoreSubmitPayload, etc.)
// are structural, so they keep resolving without re-exporting the base names.
export type {
  Channel,
  CommentComposerProps,
  CommentPayload,
  CommentSubmitHandler,
  EmailComposerProps,
  EmailPayload,
  EmailSubmitHandler,
  Field,
  Mention,
  MultiComposerProps,
  Recipient,
  RecipientSearch,
  Recipients,
  UploadedFile,
  UploadFunction,
} from "./types";
