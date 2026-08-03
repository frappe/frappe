import type { UploadedFile as EditorUploadedFile } from "frappe-ui/editor";

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

export type HeaderField = "from" | "to" | "subject" | "cc" | "bcc";

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

// --- Editing core (ComposerEditor.vue, private) -----------------------------

export interface CoreSubmitPayload {
  body: string;
  attachments: UploadedFile[];
}

interface BaseComposerProps {
  placeholder?: string;
  submitLabel?: string;
  uploadFunction?: UploadFunction;
}

export interface ComposerEditorProps extends BaseComposerProps {
  mentions?: MentionOption[];
}

/**
 * Helpers the footer `actions` slot receives to drive a custom uploader.
 * Don't call `addAttachment` if the composer was reset mid-upload.
 */
export interface ComposerActionsSlotProps {
  addAttachment: (file: UploadedFile) => void;
  setUploading: (value: boolean) => void;
}

interface BaseComposerEmits<Payload> {
  /** Fires with the built payload; the host performs the send, then `reset()`. */
  submit: [payload: Payload];
  /** Only on explicit chip removal (so the host can delete server-side). */
  "remove-attachment": [file: UploadedFile];
}

// --- EmailComposer ----------------------------------------------------------

export interface EmailPayload extends CoreSubmitPayload {
  from: string;
  subject: string;
  recipients: Recipients;
}

/** v-models: body (default), from, recipients, subject, quoted. */
export interface EmailComposerProps extends BaseComposerProps {
  /** Built-in header rows to render. Defaults to ["to", "cc", "bcc"]. */
  headerFields?: HeaderField[];
  /** Sender identities for the From row (shown when `headerFields` includes "from"). */
  senders?: Recipient[];
  /** Recipient lookup; omit for a plain creatable-email field. */
  searchRecipients?: RecipientSearch;
}

export type EmailComposerEmits = BaseComposerEmits<EmailPayload>;

export interface EmailComposerSlots {
  /** Replaces the built-in header rows; an empty template renders no header. */
  header?: () => any;
  /** Extra footer actions, beside the built-in attach button. */
  actions?: (props: ComposerActionsSlotProps) => any;
}

// --- CommentComposer ---------------------------------------------------------

export type CommentPayload = CoreSubmitPayload;

export type CommentComposerProps = ComposerEditorProps;

export type CommentComposerEmits = BaseComposerEmits<CommentPayload>;

export interface CommentComposerSlots {
  /** Extra footer actions, beside the built-in attach button. */
  actions?: (props: ComposerActionsSlotProps) => any;
}
