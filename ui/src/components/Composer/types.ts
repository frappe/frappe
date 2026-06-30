import type { UploadedFile as EditorUploadedFile } from "frappe-ui/editor";

/** A recipient chip. `label`/`image` ride along when supplied. */
export interface Recipient {
  email: string;
  label?: string;
  image?: string;
}

export interface Recipients {
  to: Recipient[];
  cc: Recipient[];
  bcc: Recipient[];
}

/** Host-supplied recipient lookup, called as the user types (and once with ""). */
export type RecipientSearch = (query: string) => Promise<Recipient[]>;

/** Optional email rows beyond the always-present "To". */
export type Field = "subject" | "cc" | "bcc";

/** A file as returned by FileUploader's `success` event. */
export interface UploadedFile {
  name: string;
  file_name: string;
  file_url: string;
  file_type: string;
  file_size?: number;
}

/** An @-mention option: `label` is shown, `value` is the inserted id. */
export interface MentionOption {
  label: string;
  value: string;
}

/** Inline-image upload handler passed to the editor; returns the editor's file shape. */
export type UploadFunction = (file: File) => Promise<EditorUploadedFile>;

// --- Base composer (Composer.vue) -----------------------------------------

/** Emitted on submit. */
export interface CoreSubmitPayload {
  body: string;
  attachments: UploadedFile[];
}

/** Host's send. Composer awaits it, manages its own pending/spinner state, and
 *  never resets the draft itself — reset (success) or not (failure) is the
 *  host's call, made via the exposed `reset()` after this resolves/throws. */
export type SubmitFunction<T> = (payload: T) => Promise<void>;

/** Props shared by every composer surface. */
export interface ComposerProps {
  placeholder?: string;
  label?: string;
  uploadFunction?: UploadFunction;
  /** @-mention options for the comment editor. */
  mentionOptions?: MentionOption[];
  onSubmit: SubmitFunction<CoreSubmitPayload>;
}

// --- EmailComposer ---------------------------------------------------------

/** Passed to `onSubmit`: the full email envelope. */
export interface EmailPayload extends CoreSubmitPayload {
  subject: string;
  recipients: Recipients;
}

/** Window-agnostic email content. Recipients, subject and body are v-models. */
export interface EmailComposerProps {
  placeholder?: string;
  label?: string;
  uploadFunction?: UploadFunction;
  /** Rows beyond "To". Defaults to ["cc", "bcc"]. */
  fields?: Field[];
  /** Recipient lookup; omit for a plain creatable-email field. */
  searchRecipients?: RecipientSearch;
  onSubmit: SubmitFunction<EmailPayload>;
}

// --- CommentComposer -------------------------------------------------------

/** A comment carries just body + attachments. */
export type CommentPayload = CoreSubmitPayload;

export type CommentComposerProps = ComposerProps;

// --- MultiComposer ---------------------------------------------------------

/** The channel MultiComposer is showing; drive it with `v-model:channel`. */
export type Channel = "email" | "comment";

/** A wrapper over EmailComposer + CommentComposer with a channel switcher. */
export interface MultiComposerProps {
  placeholder?: string;
  label?: string;
  uploadFunction?: UploadFunction;
  /** Show the window pop-out/close control. Defaults to true. */
  expandable?: boolean;
  /** Avatar URL for the collapsed trigger bar. */
  avatar?: string;
  /** Name used as the Avatar fallback initial when no image is available. */
  avatarLabel?: string;
  // email channel
  /** Rows beyond "To". Defaults to ["cc", "bcc"]. */
  fields?: Field[];
  searchRecipients?: RecipientSearch;
  onSubmit: SubmitFunction<EmailPayload>;
  // comment channel
  mentionOptions?: MentionOption[];
  onSubmitComment: SubmitFunction<CommentPayload>;
}
