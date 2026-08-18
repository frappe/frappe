# InviteUser

A Vue panel for inviting users to a Frappe app by email — over Frappe's built-in
**User Invitation** API (`frappe.core.api.user_invitation`).

The component is **UI only**. Data is a plugin the host owns: call `useInviteUser()`
to get a controller, then spread it onto the panel with `v-bind`. The panel renders
the form: a **multi-email field** that autocompletes existing users (and lets you type
brand-new addresses), a **role multi-select**, and a submit button.

The panel carries **no heading** — it renders standard frappe-ui fields with English
defaults; add your own `<h2>` above it if you want one. To relabel/localize or restyle a
field, forward props onto it with **`emailProps` / `rolesProps`** (the light path — no
slot, no re-render); to replace a field's rendering wholesale, use its **per-field slot**
(`#email` / `#roles` / `#submit`). Errors are **field-scoped** the frappe-ui way: the
controller error binds to the email field's `:error` and renders inline under it.

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
  roles: [
    { label: "Agent", value: "Agent" },
    { label: "Agent Manager", value: "Agent Manager" },
  ],
});
</script>

<template>
  <h2 class="text-lg-semibold">Invite users</h2>
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
- **Which roles** — the host supplies the picker's roles as a static list via
  `useInviteUser({ roles })`; the framework no longer derives them from the app's
  hook. At invite time the backend still **verifies** the chosen roles against the
  app's `user_invitation` hook `allowed_roles` (the default `frappe` app declares
  none and skips this check, so it trusts the supplied list). There is **no role
  hierarchy** — roles are inserted verbatim; use `transformRoles` to expand a picked
  role into a set.

A permission failure on the **invite** itself surfaces through `controller.error`,
rendered inline under the email field (the field's `:error`). A failure on a
**background** read/mutation (the pending / already-invited fetches, cancel, resend, user
search) goes to `controller.loadError` instead — kept off the email field so a failed
initial load doesn't mark an untouched input as invalid. Surface `loadError` yourself
(a banner or toast) if your host renders those flows.

## Props

Spread the controller's data + verbs via `v-bind="controller"`. To relabel/localize or
restyle a field, forward props onto it with `emailProps` / `rolesProps` — no slot, no
re-render.

| Prop               | Type                            | Default | Description                                                                                                                                                                                        |
| ------------------ | ------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `showResultToasts` | `boolean`                       | `true`  | Show the standard per-bucket success toasts (invited / already-disabled / already-pending / already-accepted). Set `false` to handle results via `@invited`.                                       |
| `emailProps`       | `Partial<MultiEmailInputProps>` | —       | Props forwarded onto the email field (`MultiEmailInput`) — e.g. `{ label, description, placeholder, size }`. The field ships with **no default description**; pass one here if you want help text. |
| `rolesProps`       | `Partial<MultiSelectProps>`     | —       | Props forwarded onto the roles field (`MultiSelect`) — e.g. `{ label, placeholder }`.                                                                                                              |
| `roles`            | `RoleOption[]`                  | `[]`    | _Controller data._ Roles offered in the picker. Comes from `useInviteUser({ roles })` via `v-bind="controller"`.                                                                                   |
| `users`            | `UserOption[]`                  | `[]`    | _Controller data._ User suggestions for the email typeahead. Driven by `searchUsers`.                                                                                                              |
| `usersLoading`     | `boolean`                       | `false` | _Controller data._ True while a user search is in flight (drives the field's loading state).                                                                                                       |
| `inviting`         | `boolean`                       | `false` | _Controller data._ True while an invite request is in flight (disables submit, shows its spinner).                                                                                                 |
| `error`            | `unknown`                       | `null`  | _Controller data._ The latest **invite** error; surfaced inline under the email field via its `:error`.                                                                                            |
| `invite`           | `(emails, roles) => Promise`    | —       | _Controller verb._ Sends the invites. Wired automatically by the panel's submit.                                                                                                                   |
| `searchUsers`      | `(query) => void`               | —       | _Controller verb._ Fetches user suggestions; the panel debounces the field's `update:query` into it (250 ms).                                                                                      |
| `load`             | `() => void`                    | —       | _Controller verb._ Lazy initial fetch; the panel calls it once on mount.                                                                                                                           |

```vue
<InviteUser
  v-bind="controller"
  :email-props="{ label: __('Invite by email') }"
  :roles-props="{ label: __('Roles') }"
/>
```

> **Precedence** for `emailProps`/`rolesProps`: the panel's English defaults < your props
> < the controlled wiring (`model-value`, `options`, `error`, query/invalid handlers). So
> you can set copy + presentation, but you can't break the field's data binding. For full
> control of the rendered field, use its slot instead (see [Slots](#slots)).

> The submit button's text is `Button`'s slot content, not a prop — there's nothing to
> forward, so retitle it via the `#submit` slot.

> The controller `error` (the **invite** error) surfaces **field-scoped** — inline under
> the email field via its `:error` prop (frappe-ui's `useInputLabeling`), not as a separate
> form-level line. Background failures land on `controller.loadError` instead, so a failed
> initial load never marks an untouched email field as invalid.

> frappe-ui has no internal i18n. The fields' default labels/placeholders are English;
> localize them through `emailProps`/`rolesProps` (or a field slot for deeper changes).

## Events

| Event     | Payload            | When                                             |
| --------- | ------------------ | ------------------------------------------------ |
| `invited` | `InviteResult`     | An invite request resolves.                      |
| `invalid` | `emails: string[]` | One or more created addresses failed validation. |
| `error`   | `unknown`          | The invite verb rejects.                         |

## Slots

Slots are the **heavy** customization tool — reach for them to replace a field's
rendering wholesale. For just copy/presentation (labels, placeholder, size), prefer
`emailProps`/`rolesProps` above. Each field is its own slot, so you override **just the
field you care about** and the rest keep their defaults; every slot's default is the
standard frappe-ui field, so passing none renders the standard panel.

| Slot     | Props                                                             | Description                 |
| -------- | ----------------------------------------------------------------- | --------------------------- |
| `email`  | `{ value, setValue, options, loading, error, search, onInvalid }` | Replace the email field.    |
| `roles`  | `{ value, setValue, options }`                                    | Replace the roles field.    |
| `submit` | `{ submit, canSubmit, inviting }`                                 | Replace the submit control. |

A slot exposes the live `value` plus a `setValue` setter (instead of leaking a writable
ref), so bind `:model-value` / `@update:model-value` in your override. Each slot is
independent — override only the ones you need and the rest keep their standard fields.

### `#email`

Scope: `{ value, setValue, options, loading, error, search, onInvalid }`. Re-render the
email field — here, localizing its label while keeping the controlled wiring:

```vue
<InviteUser v-bind="controller">
  <template #email="{ value, setValue, options, loading, error, search, onInvalid }">
    <MultiEmailInput
      :model-value="value"
      @update:model-value="setValue"
      :label="__('Invite by email')"
      :options="options"
      :loading="loading"
      :error="error"
      @update:query="search"
      @invalid="onInvalid"
    />
  </template>
</InviteUser>
```

### `#roles`

Scope: `{ value, setValue, options }`. Replace the role picker — e.g. swap `MultiSelect`
for a checkbox group, or just relabel:

```vue
<InviteUser v-bind="controller">
  <template #roles="{ value, setValue, options }">
    <MultiSelect
      :model-value="value"
      @update:model-value="setValue"
      :label="__('Access level')"
      :options="options"
    />
  </template>
</InviteUser>
```

### `#submit`

Scope: `{ submit, canSubmit, inviting }`. Replace the submit control — the place to
retitle the button (its text is slot content, not a prop) or restyle it:

```vue
<InviteUser v-bind="controller">
  <template #submit="{ submit, canSubmit, inviting }">
    <Button
      variant="solid"
      :loading="inviting"
      :disabled="!canSubmit"
      @click="submit"
    >
      {{ __('Send invitations') }}
    </Button>
  </template>
</InviteUser>
```

### All three together

```vue
<InviteUser v-bind="controller">
  <template #email="{ value, setValue, options, loading, error, search, onInvalid }">
    <MultiEmailInput
      :model-value="value"
      @update:model-value="setValue"
      :label="__('Invite by email')"
      :options="options"
      :loading="loading"
      :error="error"
      @update:query="search"
      @invalid="onInvalid"
    />
  </template>

  <template #roles="{ value, setValue, options }">
    <MultiSelect
      :model-value="value"
      @update:model-value="setValue"
      :label="__('Access level')"
      :options="options"
    />
  </template>

  <template #submit="{ submit, canSubmit, inviting }">
    <Button variant="solid" :loading="inviting" :disabled="!canSubmit" @click="submit">
      {{ __('Send invitations') }}
    </Button>
  </template>
</InviteUser>
```

> Note: when you replace the `#submit` slot, drive the button from `canSubmit` /
> `inviting` and call `submit()` — those encode the panel's rules (at least one email
> **and** one role picked, and not already inviting). A plain `type="submit"` button also
> works since the slot still sits inside the panel's `<form>`.

## `useInviteUser`

The data plugin behind the panel. Each call returns a **fresh** controller (no
module-level cache) and fetches **lazily** — call `load()` once you want the data
(the panel does this on mount).

```ts
const controller = useInviteUser({
  appName, // target app (default "frappe")
  redirectPath, // where invitees land after accepting (default "/app")
  roles, // RoleOption[] shown in the picker (host-supplied; verified at invite time)
  transformRoles, // (selected) => string[] — expand picked roles before sending
  extraParams, // extra invite_by_email params (filtered by the app's extra_invite_params hook)
});

// controller (a reactive object — don't destructure):
// data:  pendingInvites, roles, users, loading, usersLoading, inviting,
//        cancellingName, resendingName, error (invite only), loadError (background)
// verbs: invite(emails, roles), cancel(name), resend(name), searchUsers(query),
//        load() — lazy initial fetch (idempotent), reload() — refetch pending/invited
```

## Backend

Whitelisted methods called:

- `frappe.core.api.user_invitation.invite_by_email` (POST)
- `frappe.core.api.user_invitation.get_pending_invitations` (GET — auto-fetch)
- `frappe.core.api.user_invitation.cancel_invitation` (PATCH)
- `frappe.core.api.user_invitation.resend_invitation` (POST)
- `frappe.client.get_list` on `User` (email autocomplete) and `User Invitation`
  (already-invited exclusion)

## Types

`RoleOption`, `UserOption`, `PendingInvitation`, `InviteResult`,
`UseInviteUserOptions`, `InviteStore`, `InviteUserProps`, `InviteEmailSlotProps`,
`InviteRolesSlotProps`, `InviteSubmitSlotProps`.
