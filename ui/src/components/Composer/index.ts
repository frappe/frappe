// Two standalone, inline message composers built on a shared editing core.
//
//   EmailComposer    Recipient rows (To/Cc/Bcc) and a subject above the editor,
//                    with an optional collapsible quoted reply. Emits an
//                    EmailPayload; the host runs the actual send.
//   CommentComposer  The editor alone, with @-mentions — for internal notes.
//
// Both render inline, in normal document flow. A host that wants a floating,
// minimizable reply window wraps either in frappe-ui's FloatingWindow (FP1 —
// compose the atom, don't rebuild it).
//
// The shared editing core (ComposerEditor.vue) and the recipient inputs are
// internal building blocks, not part of the public surface.
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
  Field,
  MentionOption,
  Recipient,
  RecipientSearch,
  Recipients,
  UploadedFile,
  UploadFunction,
} from "./types";
