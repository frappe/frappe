// Two inline composers on a shared editing core: EmailComposer (header rows,
// quoted reply) and CommentComposer (@-mentions). Both emit a payload on
// submit — the host runs the send. For a floating reply window, wrap either
// in frappe-ui's FloatingWindow.
export { default as EmailComposer } from "./EmailComposer/EmailComposer.vue";
export { default as CommentComposer } from "./CommentComposer/CommentComposer.vue";
export type {
  CommentComposerEmits,
  CommentComposerProps,
  CommentComposerSlots,
  CommentPayload,
  EmailComposerEmits,
  EmailComposerProps,
  EmailComposerSlots,
  EmailPayload,
  MentionOption,
  Recipient,
  RecipientSearch,
  UploadedFile,
  UploadFunction,
} from "./types";
