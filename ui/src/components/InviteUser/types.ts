/**
 * Contracts for the InviteUser module — a backend-aware "invite users by email"
 * building block over Frappe's `frappe.core.api.user_invitation` API. The data
 * plugin (`useInviteUser`) owns the resources and returns an `InviteStore`; the
 * `InviteUser` panel is UI-only and renders that store via `v-bind`.
 */

import type { MultiSelectProps } from "frappe-ui";
import type { MultiEmailInputProps } from "frappe-ui/experimental";

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
  /**
   * Latest error from the invite request only; `null` while healthy. This is the
   * email-field error the panel binds to `:error` — it stays empty on a fresh form
   * even if a background fetch fails (see {@link loadError}).
   */
  error: unknown;
  /**
   * Latest error from the background resources (pending / already-invited fetches,
   * cancel, resend, user search); `null` while healthy. Kept off the email field so
   * a load/permission failure doesn't mark an untouched input as invalid — surface it
   * yourself (a banner, a toast) if your host renders those flows.
   */
  loadError: unknown;

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

/**
 * Props for the `InviteUser` panel. Spread the controller's data via
 * `v-bind="controller"`. The panel renders standard frappe-ui fields with English
 * defaults; there are no flat copy props. For light customization (relabel, localize,
 * restyle) forward props onto a field with {@link emailProps} / {@link rolesProps}; to
 * replace a field's rendering wholesale, use its per-field slot (`#email` / `#roles` /
 * `#submit`). Errors are field-scoped (the `error` below surfaces under the email
 * field), so there is no form-level error prop either.
 */
export interface InviteUserProps {
  /** Roles for the picker (controller data). */
  roles?: RoleOption[];
  /** User suggestions for the email field (controller data). */
  users?: UserOption[];
  usersLoading?: boolean;
  inviting?: boolean;
  /** Latest controller error; surfaced inline under the email field. */
  error?: unknown;
  /** Show the standard result toasts on success (set false to handle via `@invited`). */
  showResultToasts?: boolean;

  /**
   * Props forwarded onto the email field (`MultiEmailInput`). The lightweight way to
   * relabel/localize or restyle the field without overriding the `#email` slot — e.g.
   * `{ label: __('Invite by email'), size: 'lg' }`. Precedence: the panel's English
   * defaults < your props < the controlled wiring (`model-value`, `options`, `error`,
   * query/invalid handlers), so you can set copy and presentation but can't break the
   * data binding. For full control of the rendered field, use the `#email` slot instead.
   */
  emailProps?: Partial<MultiEmailInputProps>;
  /**
   * Props forwarded onto the roles field (`MultiSelect`); same precedence rules as
   * {@link emailProps}. For full control, use the `#roles` slot. The submit button's
   * text is `Button`'s slot content (not a prop), so retitle it via the `#submit` slot.
   */
  rolesProps?: Partial<MultiSelectProps>;
}

/** Scope passed to the `#email` slot — render your own email field bound to these. */
export interface InviteEmailSlotProps {
  /** Selected/typed addresses (the field's `model-value`). */
  value: string[];
  /** Write the addresses back (the field's `@update:model-value`). */
  setValue: (emails: string[]) => void;
  /** User suggestions for the typeahead. */
  options: UserOption[];
  /** True while a user search is in flight. */
  loading: boolean;
  /** Latest controller error, surfaced field-scoped via the field's `error` prop. */
  error: unknown;
  /** Drive the typeahead (already debounced); wire to the field's `@update:query`. */
  search: (query: string) => void;
  /** Report a typed address that failed validation; wire to the field's `@invalid`. */
  onInvalid: (email: string) => void;
}

/** Scope passed to the `#roles` slot — render your own roles field bound to these. */
export interface InviteRolesSlotProps {
  /** Selected role values (the field's `model-value`). */
  value: string[];
  /** Write the roles back (the field's `@update:model-value`). */
  setValue: (roles: string[]) => void;
  /** Roles offered in the picker. */
  options: RoleOption[];
}

/** Scope passed to the `#submit` slot — render your own submit control. */
export interface InviteSubmitSlotProps {
  /** Send the invites. */
  submit: () => void;
  /** False until at least one email and one role are picked (and not already inviting). */
  canSubmit: boolean;
  /** True while an invite request is in flight. */
  inviting: boolean;
}
