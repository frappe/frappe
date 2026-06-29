// Composer.vue and ComposerHeader.vue are intentionally NOT exported: they are the
// private editing core. EmailComposer owns its FloatingWindow and optionally adds a
// comment channel (`:channels="['email', 'comment']"`); CommentComposer is the
// window-agnostic comment-only surface.
export { default as EmailComposer } from "./EmailComposer/EmailComposer.vue";
export { default as CommentComposer } from "./CommentComposer/CommentComposer.vue";
// EmailComposer owns a FloatingWindow; re-export its mode type so a consumer can
// type `v-model:mode` without reaching into frappe-ui internals.
export type { WindowMode } from "frappe-ui/experimental";
// ComposerProps / CoreSubmitPayload stay internal; the comment aliases below
// (CommentComposerProps = ComposerProps, CommentPayload = CoreSubmitPayload) are
// structural, so they resolve without re-exporting the base names.
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
