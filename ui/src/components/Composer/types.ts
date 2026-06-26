/**
 * A single recipient. `email` is the address; `label` (display name) and
 * `image` (avatar URL) are optional and ride along into the chips and dropdown
 * when supplied — so a pre-filled reply keeps its names and avatars. A bare
 * email the user types becomes `{ email }`.
 */
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

/**
 * Async recipient lookup the host supplies. Called (debounced) as the user
 * types into To/Cc/Bcc, and once with `""` when a field opens, so the host can
 * search its own directory (contacts, users, …). The library stays
 * backend-agnostic — it just renders whatever Recipients you resolve.
 */
export type RecipientSearch = (query: string) => Promise<Recipient[]>;

/**
 * Email fields a host can opt into via `fields`, beyond the always-present
 * "To" row. "subject" shows statically whenever listed; "cc" / "bcc" are
 * offered as header toggles the user reveals on demand.
 */
export type Field = "subject" | "cc" | "bcc";

/** A file object, as returned by FileUploader's `success` event. */
export interface UploadedFile {
  name: string;
  file_name: string;
  file_url: string;
  file_type: string;
  /** Size in bytes, when the uploader reports it. */
  file_size?: number;
}

/**
 * One @-mention suggestion forwarded to the editor (e.g. a user or agent). The
 * host owns the source list — exactly like Helpdesk, which feeds its agent
 * store's `{ label, value }` items straight into the editor's mention extension.
 */
export interface Mention {
  label: string;
  value: string;
}

// --- Base composer (Composer.vue) -----------------------------------------

/** What the base editing surface hands to its wrapper on submit. */
export interface CoreSubmitPayload {
  body: string;
  attachments: UploadedFile[];
}

/** Handler the wrapper gives the base composer. May be async; it's awaited. */
export type CoreSubmitHandler = (
  payload: CoreSubmitPayload
) => void | Promise<void>;

/** Inline-image upload handler passed through to the TextEditor. */
export type UploadFunction = (file: File) => Promise<unknown>;

/** Props shared by every composer surface (owned by Composer.vue). */
export interface ComposerProps {
  /** localStorage key to persist the in-progress reply/quoted draft (null = don't). */
  storageKey?: string | null;
  /** Placeholder shown in the empty editor body. */
  placeholder?: string;
  /** Label for the primary send button. */
  label?: string;
  /** Inline-image upload handler forwarded to the TextEditor. */
  uploadFunction?: UploadFunction;
  /** @-mention suggestions for the editor (e.g. users/agents). Host-owned list. */
  mentions?: Mention[];
  /**
   * Signature HTML to place below the body. The host owns the content (e.g. a
   * per-identity block) and changes this when the sending identity changes; the
   * composer seeds it into an empty body and swaps it on change — but only while
   * the user hasn't written over it.
   */
  signature?: string;
  /** Send method invoked on submit. Awaited; throw (or toast + throw) to keep the draft. */
  onSubmit?: CoreSubmitHandler;
}

// --- EmailComposer ---------------------------------------------------------

/** Everything a consumer needs to send a composed email. */
export interface EmailPayload extends CoreSubmitPayload {
  subject: string;
  recipients: Recipients;
}

export type EmailSubmitHandler = (
  payload: EmailPayload
) => void | Promise<void>;

/**
 * Props for EmailComposer. Recipients, subject and body are not props — they're
 * two-way state the host drives with v-models, one source of truth (no
 * init-prop-vs-internal-state desync):
 *   `v-model:recipients` (Recipients)   `v-model:subject` (string)
 *   `v-model:body` (string)
 * Seed a reply by setting the recipients model and calling the exposed
 * `setQuotedReply()`. Attachments stay owned by the composer; an explicit
 * removal is reported via the `remove-attachment` event for server cleanup.
 */
export interface EmailComposerProps extends Omit<ComposerProps, "onSubmit"> {
  /**
   * Which fields to include beyond the always-present "To" row. List "subject"
   * to show the Subject row statically; "cc" / "bcc" are offered as header
   * toggles. Pass `[]` for a To-only composer. Defaults to `["cc", "bcc"]`.
   */
  fields?: Field[];
  /**
   * Async lookup for recipient suggestions, called as the user types in
   * To/Cc/Bcc. Omit it for a plain creatable-email field (the user can still
   * type any valid address); supply it to offer a searchable directory.
   */
  searchRecipients?: RecipientSearch;
  /**
   * Show the window control in the header — pop-out while docked, close (dock
   * back) while floating. EmailComposer owns its FloatingWindow, so this drives
   * its own window; observe or set the state with `v-model:mode`. On by default;
   * set `false` for a fixed, docked-only composer.
   */
  expandable?: boolean;
  /** Send method invoked with the full email payload. */
  onSubmit?: EmailSubmitHandler;
}

// --- MultiComposer ---------------------------------------------------------

/**
 * MultiComposer's active channel. "email" shows the recipient rows and the
 * Cc/Bcc toggles and sends via `onSubmit`; "comment" hides them and sends via
 * `onComment`. Drive/observe it with `v-model:channel`.
 */
export type Channel = "email" | "comment";

/**
 * Props for MultiComposer — an EmailComposer that can flip between an email and
 * an internal comment from a header dropdown (always switchable; that's its
 * whole purpose). It is a superset of EmailComposer: every email prop applies to
 * the email channel, plus `onComment` for the comment channel. The active
 * channel is two-way state driven with `v-model:channel`.
 */
export interface MultiComposerProps extends EmailComposerProps {
  /** Send method invoked while the composer is in the "comment" channel (no recipients). */
  onComment?: CommentSubmitHandler;
}

// --- CommentComposer -------------------------------------------------------

/** An internal comment carries just a body and any attachments. */
export type CommentPayload = CoreSubmitPayload;
export type CommentSubmitHandler = CoreSubmitHandler;

/** Comments carry no signature (that's an email concept), so it's dropped. */
export type CommentComposerProps = Omit<ComposerProps, "signature">;
