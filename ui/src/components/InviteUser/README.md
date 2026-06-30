# InviteUser

A Vue panel for inviting users to a Frappe app by email — over Frappe's built-in
**User Invitation** API (`frappe.core.api.user_invitation`).

The component is **UI only**. Data is a plugin the host owns: call `useInviteUser()`
to get a controller, then spread it onto the panel with `v-bind`. The panel renders
the form: a **multi-email field** that autocompletes existing users (and lets you type
brand-new addresses) plus a **role multi-select**.

> The email field is frappe-ui's experimental **`MultiEmailInput`**
> (`frappe-ui/experimental`) — a generic chips + typeahead control. This panel
> requires a frappe-ui build that ships it; until then, import resolution for the
> email field will fail against older pinned frappe-ui versions.

There is intentionally **no pending-invitations list** in the panel. The controller
still fetches pending invitations lazily (`pendingInvites` / `load` / `reload`) for
hosts that want to render their own, but the block doesn't ship one.

Data is fetched **lazily**: `useInviteUser()` creates a fresh controller and fetches
nothing until `load()` runs. The panel calls `load()` on mount, so a controller that
is never shown costs no requests. There is **no module-level cache** — each call
returns an independent controller (the old per-`appName` cache went stale across
user/role changes and was never evicted).

## Usage

```vue
<script setup lang="ts">
import { InviteUser, useInviteUser } from "@framework/ui/components/InviteUser";

const controller = useInviteUser({
  appName: "helpdesk",
  redirectPath: "/helpdesk",
});
</script>

<template>
  <InviteUser
    v-bind="controller"
    @invited="(r) => console.log('invited', r.invited_emails)"
    @invalid="(emails) => console.warn('rejected', emails)"
    @error="(e) => console.error(e)"
  />
</template>
```

`v-bind="controller"` spreads the controller. The controller's **verbs** (`invite`,
`searchUsers`) ride along as function props and the panel drives them itself — so the
default wiring above is zero-config: the panel collects emails + roles, calls `invite`,
shows result toasts and resets. The emitted events (`invited` / `invalid` / `error`)
are for host **side-effects** (analytics, onboarding steps), not for re-implementing
the flow.

## The email field

The panel renders frappe-ui's experimental **`MultiEmailInput`** for the email
field and wires it to the controller:

- **Suggests existing users** from the **User** doctype (enabled, non-Website users —
  not Contacts), excluding anyone already invited to the app (pending or accepted).
  The panel debounces the field's `update:query` into `controller.searchUsers`.
- Matching users show in a dropdown (name over email, with avatar); pick one with the
  mouse or keyboard. Selected addresses render as removable chips with native chip
  keyboard navigation (Delete / Backspace / Arrow / Home / End) courtesy of reka-ui's
  `TagsInput`.
- Typing a brand-new address shows an explicit **Invite "&lt;email&gt;"** row (via the
  `create-label` prop); typed addresses are validated (a practical email check) and a
  failure surfaces through `@invalid`. Users picked from the list are already valid.

See `frappe-ui/experimental`'s `MultiEmailInput` docs for the full prop/slot surface.

## Backend requirements & constraints

The API is permission-gated by each app's `user_invitation` hook (`hooks.py`):

- **Who can invite** — every method calls `frappe.only_for(allowed_roles.keys())`.
  With the framework's default hook, only **System Managers** may invite for the
  default `app_name="frappe"`. Apps usually pass their own `appName` whose hook lists
  the inviter roles.
- **Which roles** — the picker fetches the **grantable** roles for the app via
  `get_invitable_roles` (on mount, through `load()`), derived from the hook's
  `allowed_roles` and scoped to the
  caller. For `app_name="frappe"` (no declared roles) it falls back to all enabled,
  assignable roles. There is **no role hierarchy** — roles are inserted verbatim; use
  `transformRoles` to expand a picked role into a set.

A permission failure surfaces through `controller.error` (and the panel's `#error` slot).

## Props

Spread the controller's data + verbs via `v-bind="controller"`; set presentation
props directly.

| Prop               | Type                        | Description                                                               |
| ------------------ | --------------------------- | ------------------------------------------------------------------------- |
| `title`            | `string` (`'Invite users'`) | Header title.                                                             |
| `showResultToasts` | `boolean` (`true`)          | Show the standard per-bucket toasts on success.                           |
| `emailLabel`       | `string`                    | Email field label.                                                        |
| `emailHint`        | `string`                    | Helper text under the email field.                                        |
| `rolesLabel`       | `string`                    | Roles field label.                                                        |
| `rolesPlaceholder` | `string`                    | Roles field placeholder.                                                  |
| `submitLabel`      | `string`                    | Submit button label.                                                      |
| `errorText`        | `string`                    | Fallback for the default `#error` slot when the error carries no message. |
| _controller data_  | via `v-bind="controller"`   | `roles`, `users`, `rolesLoading`, `usersLoading`, `inviting`, `error`.    |
| _controller verbs_ | via `v-bind="controller"`   | `invite`, `searchUsers`, `load` (function props).                         |

> frappe-ui has no internal i18n, so the copy props above carry English defaults
> (the same pattern as frappe-ui's own `placeholder`/`emptyText`). Pass translated
> strings from the host to localize.

## Events

| Event     | Payload            | When                                             |
| --------- | ------------------ | ------------------------------------------------ |
| `invited` | `InviteResult`     | An invite request resolves.                      |
| `invalid` | `emails: string[]` | One or more created addresses failed validation. |
| `error`   | `unknown`          | The invite verb rejects.                         |

## Slots

Every slot has a default, so passing none renders the standard panel.

| Slot     | Props                                                                                             | Description             |
| -------- | ------------------------------------------------------------------------------------------------- | ----------------------- |
| `header` | `{ title }`                                                                                       | Replace the header.     |
| `form`   | `{ emails, roles, roleOptions, userOptions, inviting, usersLoading, error, searchUsers, submit }` | Replace the whole form. |
| `error`  | `{ error }`                                                                                       | Shown on a failure.     |

## `useInviteUser`

The data plugin behind the panel. Each call returns a **fresh** controller (no
module-level cache) and fetches **lazily** — call `load()` once you want the data
(the panel does this on mount).

```ts
const controller = useInviteUser({
  appName, // target app (default "frappe")
  redirectPath, // where invitees land after accepting (default "/app")
  transformRoles, // (selected) => string[] — expand picked roles before sending
  extraParams, // extra invite_by_email params (filtered by the app's extra_invite_params hook)
});

// controller (a reactive object — don't destructure):
// data:  pendingInvites, roles, users, loading, rolesLoading, usersLoading, inviting,
//        cancellingName, resendingName, error
// verbs: invite(emails, roles), cancel(name), resend(name), searchUsers(query),
//        load() — lazy initial fetch (idempotent), reload() — refetch roles/pending/invited
```

## Backend

Whitelisted methods called:

- `frappe.core.api.user_invitation.invite_by_email` (POST)
- `frappe.core.api.user_invitation.get_invitable_roles` (GET — the role picker)
- `frappe.core.api.user_invitation.get_pending_invitations` (GET — auto-fetch)
- `frappe.core.api.user_invitation.cancel_invitation` (PATCH)
- `frappe.core.api.user_invitation.resend_invitation` (POST)
- `frappe.client.get_list` on `User` (email autocomplete) and `User Invitation`
  (already-invited exclusion)

## Types

`RoleOption`, `UserOption`, `PendingInvitation`, `InviteResult`,
`UseInviteUserOptions`, `InviteStore`, `InviteUserProps`, `InviteFormSlotProps`.
