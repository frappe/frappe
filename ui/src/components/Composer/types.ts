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

/** Email header rows the composer can render. */
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

/** Built body + attachments, emitted on `submit`. */
export interface CoreSubmitPayload {
  body: string;
  attachments: UploadedFile[];
}

/** Props shared by every composer surface. */
interface BaseComposerProps {
  placeholder?: string;
  /** Label on the submit button. */
  submitLabel?: string;
  uploadFunction?: UploadFunction;
}

/** The shared editing core. */
export interface ComposerEditorProps extends BaseComposerProps {
  /** @-mention options for the editor. */
  mentions?: MentionOption[];
}

/** Helpers the footer `actions` slot receives to drive a custom uploader. */
export interface ComposerActionsSlotProps {
  addAttachment: (file: UploadedFile) => void;
  setUploading: (value: boolean) => void;
}

/** Emitted by both composers. The host runs the send and resets when done. */
interface BaseComposerEmits<Payload> {
  /** Fires with the built payload; the host performs the send, then `reset()`. */
  submit: [payload: Payload];
  /** Only on explicit chip removal (so the host can delete server-side). */
  "remove-attachment": [file: UploadedFile];
}

// --- EmailComposer ----------------------------------------------------------

/** Emitted on `submit`: the full email envelope. */
export interface EmailPayload extends CoreSubmitPayload {
  from: string;
  subject: string;
  recipients: Recipients;
}

/** Email content. Body (`v-model`), from, recipients, subject and quoted are models. */
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
  /**
   * Replaces the built-in header rows when provided — with custom content,
   * or empty (`<template #header />`) to render no header at all.
   */
  header?: () => any;
  /** Extra footer actions, beside the built-in attach button. */
  actions?: (props: ComposerActionsSlotProps) => any;
}

// --- CommentComposer ---------------------------------------------------------

/** A comment carries just body + attachments. */
export type CommentPayload = CoreSubmitPayload;

export type CommentComposerProps = ComposerEditorProps;

export type CommentComposerEmits = BaseComposerEmits<CommentPayload>;

export interface CommentComposerSlots {
  /** Extra footer actions, beside the built-in attach button. */
  actions?: (props: ComposerActionsSlotProps) => any;
}
