import { translate as __ } from "../../utils/translate";
import type {
  AccountForm,
  AuthKind,
  EmailAccount,
  EmailAccountDoc,
  EmailService,
  FieldError,
} from "./types";

// served by frappe, so Desk's Add Email Account dialog uses the same files
const LOGOS = "/assets/frappe/images/email-providers/";
const FRAPPE_CLOUD_RELAY = "frappe-cloud-relay:";
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// getters, so the text is translated when it renders rather than at import, before the host
// has loaded its translations
export const services: EmailService[] = [
  {
    service: "GMail",
    label: "Gmail",
    logo: LOGOS + "gmail.png",
    kind: "password",
    get help() {
      return __("Needs two-factor authentication and an app password.");
    },
    helpLink: "https://support.google.com/accounts/answer/185833",
  },
  {
    service: "Outlook.com",
    label: "Outlook",
    logo: LOGOS + "outlook.png",
    kind: "password",
    get help() {
      return __("Needs two-factor authentication and an app password.");
    },
    helpLink:
      "https://support.microsoft.com/en-us/account-billing/how-to-get-and-use-app-passwords-5896ed9b-4263-e681-128a-a6f2979a7944",
  },
  {
    service: "Frappe Mail",
    label: "Frappe Mail",
    logo: LOGOS + "frappe-mail.svg",
    kind: "frappe-mail",
    get help() {
      return __("Needs the API key and secret of your Frappe Mail account.");
    },
    helpLink: "https://github.com/frappe/mail",
  },
  {
    service: "Yahoo Mail",
    label: "Yahoo",
    logo: LOGOS + "yahoo.png",
    kind: "password",
    get help() {
      return __("Needs two-factor authentication and an app password.");
    },
    helpLink: "https://help.yahoo.com/kb/SLN15241.html",
  },
  {
    service: "Yandex.Mail",
    label: "Yandex",
    logo: LOGOS + "yandex.png",
    kind: "password",
    get help() {
      return __("Needs two-factor authentication and an app password.");
    },
    helpLink: "https://yandex.com/support/id/authorization/app-passwords.html",
  },
  {
    service: "Sendgrid",
    label: "SendGrid",
    logo: LOGOS + "sendgrid.png",
    kind: "password",
    outgoingOnly: true,
  },
  {
    service: "SparkPost",
    label: "SparkPost",
    logo: LOGOS + "sparkpost.webp",
    kind: "password",
    outgoingOnly: true,
  },
  {
    service: "",
    get label() {
      return __("Custom email");
    },
    kind: "custom",
  },
];

export function serviceOf(
  account: Pick<EmailAccountDoc, "service">,
): EmailService {
  return (
    services.find((s) => s.service === (account.service || "")) ??
    services.at(-1)!
  );
}

/** The address under an account's name, or its service when the name is the address. */
export function subtitle(
  account: Pick<EmailAccountDoc, "email_id" | "email_account_name" | "service">,
): string {
  return account.email_id === account.email_account_name
    ? serviceOf(account).label
    : account.email_id;
}

// Desk keeps the same table in email_account.js (frappe.email_defaults)
const SERVERS: Record<string, Partial<EmailAccountDoc>> = {
  GMail: {
    email_server: "imap.gmail.com",
    incoming_port: 993,
    use_ssl: 1,
    smtp_server: "smtp.gmail.com",
    smtp_port: 587,
    use_tls: 1,
  },
  "Outlook.com": {
    email_server: "imap-mail.outlook.com",
    use_ssl: 1,
    smtp_server: "smtp-mail.outlook.com",
    smtp_port: 587,
    use_tls: 1,
  },
  "Yahoo Mail": {
    email_server: "imap.mail.yahoo.com",
    use_ssl: 1,
    smtp_server: "smtp.mail.yahoo.com",
    smtp_port: 587,
    use_tls: 1,
  },
  "Yandex.Mail": {
    email_server: "imap.yandex.com",
    use_ssl: 1,
    smtp_server: "smtp.yandex.com",
    smtp_port: 587,
    use_tls: 1,
  },
  Sendgrid: { smtp_server: "smtp.sendgrid.net", smtp_port: 587, use_tls: 1 },
  SparkPost: {
    smtp_server: "smtp.sparkpostmail.com",
    smtp_port: 587,
    use_tls: 1,
  },
};

export function emptyForm(account?: Partial<EmailAccountDoc>): AccountForm {
  return {
    email_account_name: account?.email_account_name ?? "",
    email_id: account?.email_id ?? "",
    password: "",
    frappe_mail_site: account?.frappe_mail_site ?? "",
    api_key: account?.api_key ?? "",
    api_secret: "",
    domain: account?.domain ?? "",
    email_server: account?.email_server ?? "",
    incoming_port: account ? String(account.incoming_port || "") : "993",
    smtp_server: account?.smtp_server ?? "",
    smtp_port: account ? String(account.smtp_port || "") : "587",
    use_ssl: account ? Boolean(account.use_ssl) : true,
    use_starttls: Boolean(account?.use_starttls),
    use_tls: account ? Boolean(account.use_tls) : true,
    use_ssl_for_outgoing: Boolean(account?.use_ssl_for_outgoing),
    enable_incoming: account ? Boolean(account.enable_incoming) : true,
    enable_outgoing: account ? Boolean(account.enable_outgoing) : true,
  };
}

const CUSTOM_SERVER_FIELDS = [
  "domain",
  "email_server",
  "incoming_port",
  "smtp_server",
  "smtp_port",
  "use_ssl",
  "use_starttls",
  "use_tls",
  "use_ssl_for_outgoing",
] as const;

/** The fields of `form` that `service` stores, as Email Account values. */
export function credentials(
  service: EmailService,
  form: AccountForm,
): Record<string, unknown> {
  const values: Record<string, unknown> = {
    email_id: form.email_id,
    enable_incoming: service.outgoingOnly ? 0 : Number(form.enable_incoming),
    enable_outgoing: Number(form.enable_outgoing),
  };
  if (service.kind === "frappe-mail") {
    values.frappe_mail_site = form.frappe_mail_site;
    values.api_key = form.api_key;
    if (form.api_secret) values.api_secret = form.api_secret;
    return values;
  }
  if (form.password) values.password = form.password;
  if (service.kind === "custom") {
    for (const field of CUSTOM_SERVER_FIELDS) {
      const value = form[field];
      values[field] = typeof value === "boolean" ? Number(value) : value;
    }
  }
  return values;
}

/** A new Email Account for `service`, ready for `frappe.client.insert`. */
export function newAccount(
  service: EmailService,
  form: AccountForm,
  appendTo: string,
) {
  const imap = service.kind !== "frappe-mail" && !service.outgoingOnly;
  return {
    doctype: "Email Account",
    email_account_name: form.email_account_name,
    service: service.service,
    email_sync_option: "ALL",
    initial_sync_count: 100,
    create_contact: 1,
    track_email_status: 1,
    use_imap: Number(imap),
    imap_folder: imap ? [{ folder_name: "INBOX", append_to: appendTo }] : [],
    ...(service.kind === "frappe-mail" ||
    (service.kind === "custom" && form.domain)
      ? { append_to: appendTo }
      : {}),
    ...SERVERS[service.service],
    ...credentials(service, form),
  };
}

const SIGN_IN_STARTED = "email_oauth_sign_in_started";

/** Marks this tab as having left for a new mailbox's sign-in, so its landing can be trusted. */
export function markSignInStarted() {
  try {
    sessionStorage.setItem(SIGN_IN_STARTED, "1");
  } catch {}
}

/** Whether this tab left for a new mailbox's sign-in; clears the mark. */
export function takeSignInStarted() {
  try {
    const started = sessionStorage.getItem(SIGN_IN_STARTED) === "1";
    sessionStorage.removeItem(SIGN_IN_STARTED);
    return started;
  } catch {
    return false;
  }
}

/** The directions `account` sends or receives that no account in `accounts` is the default for. */
export function missingDefaults(
  accounts: Pick<EmailAccount, "default_incoming" | "default_outgoing">[],
  account: Record<"enable_incoming" | "enable_outgoing", number>,
) {
  return (["incoming", "outgoing"] as const).filter(
    (kind) =>
      account[`enable_${kind}`] && !accounts.some((a) => a[`default_${kind}`]),
  );
}

/** The first problem with `form`, and the field it is on. A blank secret is fine when editing. */
export function validate(
  service: EmailService,
  form: AccountForm,
  editing = false,
  oauth = false,
): FieldError | undefined {
  if (!form.email_account_name.trim())
    return {
      field: "email_account_name",
      message: __("Account name is required"),
    };
  if (!EMAIL.test(form.email_id))
    return { field: "email_id", message: __("Enter a valid email address") };
  if (oauth) return;
  if (service.kind === "frappe-mail") {
    if (!form.frappe_mail_site)
      return {
        field: "frappe_mail_site",
        message: __("Frappe Mail site is required"),
      };
    if (!form.api_key)
      return { field: "api_key", message: __("API key is required") };
    if (!form.api_secret && !editing)
      return { field: "api_secret", message: __("API secret is required") };
    return;
  }
  if (service.kind === "custom" && !form.domain) {
    if (
      !form.email_server &&
      !form.smtp_server &&
      (form.enable_incoming || form.enable_outgoing)
    )
      return {
        field: "domain",
        message: __("Pick an email domain or enter the server settings"),
      };
    if (form.enable_incoming && !form.email_server)
      return {
        field: "email_server",
        message: __("Incoming server is required"),
      };
    if (form.enable_outgoing && !form.smtp_server)
      return {
        field: "smtp_server",
        message: __("Outgoing server is required"),
      };
  }
  if (!form.password && !editing)
    return { field: "password", message: __("Password is required") };
}

export function authKind(account: EmailAccountDoc): AuthKind {
  if (account.service === "Frappe Mail") return "frappe-mail";
  if (account.auth_method !== "OAuth") return "password";
  return account.token_uri?.startsWith(FRAPPE_CLOUD_RELAY)
    ? "oauth"
    : "oauth-custom";
}

/**
 * Text for a sign-in result, in the words of the provider that signed in when it has its own;
 * both come from the URL, so neither is ever shown as is.
 */
export function oauthMessage(result: string, provider?: string | null): string {
  const providerMessages: Record<string, Record<string, string>> = {
    microsoft: {
      admin_approval: __("Your Microsoft 365 admin must approve Frappe first."),
      smtp_disabled: __(
        "SMTP AUTH is turned off for this mailbox. Ask your Microsoft 365 admin to turn on Authenticated SMTP for it.",
      ),
      smtp_disabled_personal: __(
        "Microsoft doesn't let this Outlook.com mailbox send email from other apps. Please use a Microsoft 365 work mailbox.",
      ),
      imap_disabled: __(
        "IMAP is turned off for this mailbox. Turn it on in Outlook settings or ask your admin.",
      ),
    },
  };
  const messages: Record<string, string> = {
    cancelled: __("Sign-in was cancelled."),
    admin_approval: __("Your admin must approve Frappe first."),
    expired: __("Sign-in took too long. Please try again."),
    smtp_disabled: __(
      "SMTP is turned off for this mailbox. Ask your admin to turn it on.",
    ),
    smtp_disabled_personal: __(
      "This mailbox can't send email from other apps. Please use a work mailbox.",
    ),
    imap_disabled: __(
      "IMAP is turned off for this mailbox. Turn it on in your mail settings or ask your admin.",
    ),
    already_connected: __("This mailbox is already connected."),
    wrong_mailbox: __(
      "You signed in to a different mailbox. Sign in to this account's mailbox.",
    ),
    not_team_member: __(
      "Only members of this site's Frappe Cloud team can connect a mailbox. Log in to Frappe Cloud in this browser, then try again.",
    ),
  };
  return (
    providerMessages[provider ?? ""]?.[result] ??
    messages[result] ??
    __("Couldn't connect. Please try again.")
  );
}

/** The provider's help page for fixing a sign-in result, when it has one. */
export function oauthHelpLink(
  result: string,
  provider?: string | null,
): string | undefined {
  const links: Record<string, Record<string, string>> = {
    microsoft: {
      smtp_disabled:
        "https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/authenticated-client-smtp-submission#enable-smtp-auth-for-specific-mailboxes",
    },
  };
  return links[provider ?? ""]?.[result];
}

/** `address` if it looks like an email address, else null; it comes from the URL. */
export function mailboxAddress(address?: string | null): string | null {
  return address && address.length <= 254 && EMAIL.test(address)
    ? address
    : null;
}

export function errorText(e: unknown): string {
  const { messages, message } = (e ?? {}) as {
    messages?: unknown;
    message?: string;
  };
  if (Array.isArray(messages) && messages.length) return messages.join(" ");
  return message ?? "";
}

/**
 * Whether the host's boot says the site is on Frappe Cloud V2, the only place a mailbox can
 * sign in in one click. Read on use, as the host may set it after this module loads.
 */
export function isV2Site(): boolean {
  const host = globalThis as {
    is_v2_site?: boolean;
    frappe?: { boot?: { is_v2_site?: boolean } };
  };
  return Boolean(host.is_v2_site ?? host.frappe?.boot?.is_v2_site);
}

/**
 * The services a new mailbox can sign in to in one click, each with its sign-in's name, such as
 * `{"Outlook.com": "Outlook"}`, from the host's boot; empty off Frappe Cloud V2.
 */
export function oneClickServices(): Record<string, string> {
  const host = globalThis as {
    one_click_email_services?: Record<string, string>;
    frappe?: { boot?: { one_click_email_services?: Record<string, string> } };
  };
  return (
    host.one_click_email_services ??
    host.frappe?.boot?.one_click_email_services ??
    {}
  );
}

export function reconnectable(
  account: Pick<EmailAccount, "authKind">,
): boolean {
  return (
    account.authKind === "oauth-custom" ||
    (isV2Site() && account.authKind === "oauth")
  );
}

/** Whether `account` was set up by hand on a site that offers one-click sign-in. */
export function manualSetup(account: Pick<EmailAccount, "authKind">): boolean {
  return (
    isV2Site() &&
    (account.authKind === "password" || account.authKind === "oauth-custom")
  );
}

export function deskUrl(name: string): string {
  return `/desk/email-account/${encodeURIComponent(name)}`;
}
