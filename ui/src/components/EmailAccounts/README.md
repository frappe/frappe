# EmailAccounts

The Email Accounts settings panel: list the site's mailboxes, pick the default incoming and
outgoing account, add a mailbox (password, Frappe Mail, custom IMAP/SMTP, or one-click
sign-in through Frappe Cloud), edit one, and reconnect a mailbox whose sign-in has expired.

It reads and writes **Email Account** through Frappe's own methods (`frappe.client.*`,
`email_oauth.get_one_click_providers`, `email_oauth.initiate_mailbox_connect`,
`connected_app.has_token`, `pull_emails`), so any app can host it. The host passes in only what
is app-specific.

## Usage

```vue
<script setup lang="ts">
import { EmailAccounts } from "@framework/ui/EmailAccounts";

const unsaved = ref(false);
</script>

<template>
  <EmailAccounts
    doctype="HD Ticket"
    v-model:dirty="unsaved"
    @created="(service) => onboarding.done('setup_email_account')"
  />
</template>
```

- **`doctype`**: the DocType incoming mail is appended to.
- **`providers`**: the Email Account `service` values to offer tiles for when adding an
  account, such as `["GMail", "Outlook.com", ""]`, where `""` is Custom email. All of them by
  default.
- **`created(service)`**: a mailbox was added, with a password or API key, or by one-click
  sign-in, for host side effects such as onboarding steps and telemetry. A reconnect is not a
  new mailbox and does not emit it.
- **`dirty`**: true while an add or edit form has unsaved changes, false on the list, after a
  save, after confirming Back, and when the panel unmounts. The panel's own Back asks before
  dropping changes; the host uses `dirty` to guard its own navigation, such as closing its
  settings dialog or switching to another settings screen. Unmounting the panel drops the draft.
- **One-click sign-in** is offered where the site supports it, which the panel asks Frappe
  (`get_one_click_providers`, only on Frappe Cloud v2 sites). Elsewhere the Outlook tile falls
  back to the password form. Sign-in leaves the page and lands back on it with
  `?email_oauth=<result>&email_oauth_mailbox=<address>` appended. The panel reads both when it
  mounts and removes them from the URL. The host's only job is to open the panel when the page
  loads with `email_oauth` in its URL. `connected` and `reconnected` show a toast; any other
  code shows a fixed message in the list, naming the mailbox only when it is an email address.
- The panel saves and reloads by itself. When loading fails, the list shows the error with Retry.

## Account states

See `CONTEXT.md` (**Auth kind**, **Account status**, **Reconnect**).

The panel fills its container's height, with a fixed header and a scrolling body, and adds no
outer padding: the host pads it to line up with its own settings screens. Its body bleeds 12px
into that padding on each side, for row hovers, focus rings and the scrollbar, so the host pads
it by at least that much. Mount it in a container with a height, such as a settings dialog's
content pane. Its toasts and its unsaved changes confirm render through frappe-ui's `toast` and
`dialog`, so the app must mount `FrappeUIProvider`.
