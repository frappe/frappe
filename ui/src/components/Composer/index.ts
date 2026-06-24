// Composer.vue and ComposerHeader.vue are intentionally NOT exported: they are the
// private editing core. Consumers pick a channel (EmailComposer / CommentComposer);
// a new channel means a new thin wrapper, never importing the base directly.
export { default as EmailComposer } from "./EmailComposer/EmailComposer.vue";
export { default as CommentComposer } from "./CommentComposer/CommentComposer.vue";
// ComposerProps, CoreSubmitPayload, and CoreSubmitHandler are the private core's
// contract and stay internal alongside Composer.vue. The channel aliases below
// (CommentComposerProps = ComposerProps, CommentPayload = CoreSubmitPayload, etc.)
// are structural, so they keep resolving without re-exporting the base names.
export type {
  CommentComposerProps,
  CommentPayload,
  CommentSubmitHandler,
  EmailComposerProps,
  EmailPayload,
  EmailSubmitHandler,
  Mention,
  OptionalField,
  Recipient,
  Recipients,
  UploadedFile,
  UploadFunction,
} from "./types";
