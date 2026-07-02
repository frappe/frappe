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

/** Built body + attachments, emitted on `submit`. */
export interface CoreSubmitPayload {
  body: string;
  attachments: UploadedFile[];
}

/** Fields shared by every composer surface. */
interface BaseComposerProps {
  placeholder?: string;
  label?: string;
  uploadFunction?: UploadFunction;
  /** Wrap the composer in a ComposerWindow (collapsible trigger bar + pop-out/dock),
   *  instead of always-visible content. Defaults to false. */
  expandable?: boolean;
  /** Trigger-bar avatar, used when `expandable` is true. */
  avatar?: string;
  avatarLabel?: string;
}

/** Props shared by every composer surface. */
export interface ComposerProps extends BaseComposerProps {
  /** @-mention options for the comment editor. */
  mentionOptions?: MentionOption[];
}

// --- EmailComposer ---------------------------------------------------------

/** Emitted on `submit`: the full email envelope. */
export interface EmailPayload extends CoreSubmitPayload {
  subject: string;
  recipients: Recipients;
}

/** Window-agnostic email content. Recipients, subject and body are v-models. */
export interface EmailComposerProps extends BaseComposerProps {
  /** Rows beyond "To". Defaults to ["cc", "bcc"]. */
  fields?: Field[];
  /** Recipient lookup; omit for a plain creatable-email field. */
  searchRecipients?: RecipientSearch;
}

// --- CommentComposer -------------------------------------------------------

/** A comment carries just body + attachments. */
export type CommentPayload = CoreSubmitPayload;

export type CommentComposerProps = ComposerProps;

// --- MultiComposer ---------------------------------------------------------

/** The channel MultiComposer is showing; drive it with `v-model:channel`. */
export type Channel = "email" | "comment";

/** A wrapper over EmailComposer + CommentComposer with a channel switcher. */
export interface MultiComposerProps extends BaseComposerProps {
  // email channel
  /** Rows beyond "To". Defaults to ["cc", "bcc"]. */
  fields?: Field[];
  searchRecipients?: RecipientSearch;
  // comment channel
  mentionOptions?: MentionOption[];
}
