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

/** Inline-image upload handler passed to the editor. */
export type UploadFunction = (file: File) => Promise<unknown>;

// --- Base composer (Composer.vue) -----------------------------------------

/** Emitted on submit. */
export interface CoreSubmitPayload {
  body: string;
  attachments: UploadedFile[];
}

/** Props shared by every composer surface. */
export interface ComposerProps {
  placeholder?: string;
  label?: string;
  uploadFunction?: UploadFunction;
  /** @-mention options (comments only; EmailComposer omits this). */
  mentionOptions?: MentionOption[];
  /** Send in flight — host-owned; drives the primary button's spinner. */
  loading?: boolean;
}

// --- EmailComposer ---------------------------------------------------------

/** A channel the composer can send on; drive the active one with `v-model:channel`. */
export type Channel = "email" | "comment";

/** Emitted on `submit`: the full email envelope. */
export interface EmailPayload extends CoreSubmitPayload {
  subject: string;
  recipients: Recipients;
}

/** Recipients, subject and body are v-models, not props. */
export interface EmailComposerProps extends ComposerProps {
  /** Rows beyond "To". Defaults to ["cc", "bcc"]. */
  fields?: Field[];
  /** Recipient lookup; omit for a plain creatable-email field. */
  searchRecipients?: RecipientSearch;
  /** Show the window pop-out/close control. Defaults to true. */
  expandable?: boolean;
  /** Channels offered. More than one turns the title into a switcher and enables
   *  the `submit-comment` event. Defaults to ["email"]. */
  channels?: Channel[];
}

// --- CommentComposer -------------------------------------------------------

/** A comment carries just body + attachments. */
export type CommentPayload = CoreSubmitPayload;

export type CommentComposerProps = ComposerProps;
