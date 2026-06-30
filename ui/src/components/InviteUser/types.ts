/**
 * Contracts for the InviteUser module — a backend-aware "invite users by email"
 * building block over Frappe's `frappe.core.api.user_invitation` API. The data
 * plugin (`useInviteUser`) owns the resources and returns an `InviteStore`; the
 * `InviteUser` panel is UI-only and renders that store via `v-bind`.
 */

/** A selectable role in the form's role picker. `value` is the Frappe Role name. */
export interface RoleOption {
  label: string;
  value: string;
  description?: string;
}

/** A user suggested in the email field. `value` is the user's email (their `User` name). */
export interface UserOption {
  label: string;
  value: string;
  /** Avatar image URL (the User's `user_image`), if any. */
  avatar?: string;
}

/** One pending invitation row, as returned by `get_pending_invitations`. */
export interface PendingInvitation {
  name: string;
  email: string;
  roles: string[];
}

/**
 * Bucketed outcome of `invite_by_email`: which addresses were newly invited vs.
 * skipped (already pending/accepted, or a disabled user). Drives the result toasts.
 */
export interface InviteResult {
  disabled_user_emails: string[];
  accepted_invite_emails: string[];
  pending_invite_emails: string[];
  invited_emails: string[];
}

/** Options for the `useInviteUser` data plugin. */
export interface UseInviteUserOptions {
  /**
   * Target app the invitations belong to (the API's `app_name`). Defaults to
   * `"frappe"`. Determines who may invite (the app's `user_invitation` hook gates
   * the API) — with the framework default, only System Managers may invite for the
   * `frappe` app.
   */
  appName?: string;
  /** Where an invitee lands after accepting (the API's `redirect_to_path`). Defaults to `/app`. */
  redirectPath?: string;
  /**
   * Map the picked roles to the roles actually sent to the backend, e.g. an app
   * that expands "Admin" → ["Agent", "Agent Manager", "Admin"]. Defaults to identity;
   * the framework itself has no role hierarchy and inserts `roles` verbatim.
   */
  transformRoles?: (selected: string[]) => string[];
  /**
   * Extra params forwarded to `invite_by_email` (filtered server-side by the app's
   * `extra_invite_params` hook). Anything not whitelisted by the app is ignored.
   */
  extraParams?: Record<string, unknown>;
  /**
   * Roles offered in the picker. The host supplies these — the framework no longer
   * derives them from the app's `user_invitation` hook. The backend still verifies
   * them at invite time for apps that declare an `allowed_roles` hook (the default
   * `frappe` app skips role validation, so it trusts this list).
   */
  roles?: RoleOption[];
}

/**
 * The reactive controller `useInviteUser` returns. Data members read as live
 * values under `v-bind="controller"` (it's a `reactive` object, so refs unwrap —
 * don't destructure it); verbs are methods the host wires to the panel's events.
 */
export interface InviteStore {
  /** Current pending invitations for `appName` (auto-fetched; no built-in UI renders them). */
  pendingInvites: PendingInvitation[];
  /** Roles offered in the picker — the static list passed to `useInviteUser({ roles })`. */
  roles: RoleOption[];
  /** Latest user suggestions for the email field (driven by `searchUsers`). */
  users: UserOption[];
  /** True while the pending list is (re)loading. */
  loading: boolean;
  /** True while a user search is in flight. */
  usersLoading: boolean;
  /** True while an invite request is in flight. */
  inviting: boolean;
  /** The invite name currently being cancelled, or `null`. */
  cancellingName: string | null;
  /** The invite name currently being resent, or `null`. */
  resendingName: string | null;
  /** Latest error from any resource; `null` while healthy. */
  error: unknown;

  /** Send invites. `emails` is a comma/semicolon/newline-separated string. Resolves the buckets. */
  invite: (emails: string, roles: string[]) => Promise<InviteResult>;
  /** Cancel a pending invitation by its name. */
  cancel: (name: string) => Promise<void>;
  /** Resend a pending invitation's email by its name. */
  resend: (name: string) => Promise<void>;
  /** Fetch user suggestions for the email field, matched by `query`. */
  searchUsers: (query: string) => void;
  /**
   * Trigger the lazy initial fetch (roles, pending, already-invited). Idempotent —
   * runs once per controller; the `InviteUser` panel calls it on mount. Composable-only
   * hosts (no panel) should call it themselves once they want the data.
   */
  load: () => void;
  /** Re-fetch roles, the pending list, and the already-invited set the email field excludes. */
  reload: () => void;
}

/** Props for the `InviteUser` panel. Spread the controller's data via `v-bind="controller"`. */
export interface InviteUserProps {
  /** Roles for the picker (controller data). */
  roles?: RoleOption[];
  /** User suggestions for the email field (controller data). */
  users?: UserOption[];
  usersLoading?: boolean;
  inviting?: boolean;
  error?: unknown;
  /** Header title. */
  title?: string;
  /** Show the standard result toasts on success (set false to handle via `@invited`). */
  showResultToasts?: boolean;

  // --- Customisable copy (frappe-ui has no internal i18n; strings are props with
  // English defaults, matching how its own components expose `placeholder`/`emptyText`). ---
  /** Label for the email field. */
  emailLabel?: string;
  /** Helper text beneath the email field. */
  emailHint?: string;
  /** Label for the roles field. */
  rolesLabel?: string;
  /** Placeholder for the roles field. */
  rolesPlaceholder?: string;
  /** Submit button label. */
  submitLabel?: string;
  /** Fallback text for the default `#error` slot when the error carries no message. */
  errorText?: string;
}

/** Scope passed to the `#form` slot. */
export interface InviteFormSlotProps {
  emails: string[];
  roles: string[];
  roleOptions: RoleOption[];
  userOptions: UserOption[];
  inviting: boolean;
  /** True while the user typeahead search is in flight. */
  usersLoading: boolean;
  /** Latest controller error, or `null`. */
  error: unknown;
  /** Drive the email field's user typeahead. */
  searchUsers: (query: string) => void;
  submit: () => void;
}
