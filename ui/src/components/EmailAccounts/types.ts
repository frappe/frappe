/** Providers the panel signs a mailbox in with through Frappe Cloud. */
export type OneClickProvider = "microsoft";

export type AuthKind = "password" | "frappe-mail" | "oauth" | "oauth-custom";

/** An account's state, shown in the list's status badge. */
export type AccountStatus = "active" | "needs-reconnect";

export interface EmailAccountDoc {
  name: string;
  email_account_name: string;
  email_id: string;
  service: string;
  auth_method: "Basic" | "OAuth";
  connected_app?: string;
  /** The Connected App's, read through `connected_app`. */
  token_uri?: string | null;
  connected_user?: string;
  backend_app_flow?: 0 | 1;
  enable_incoming: 0 | 1;
  enable_outgoing: 0 | 1;
  default_incoming: 0 | 1;
  default_outgoing: 0 | 1;
  domain?: string;
  email_server?: string;
  incoming_port?: string | number;
  smtp_server?: string;
  smtp_port?: string | number;
  use_ssl?: 0 | 1;
  use_starttls?: 0 | 1;
  use_tls?: 0 | 1;
  use_ssl_for_outgoing?: 0 | 1;
  frappe_mail_site?: string;
  api_key?: string;
}

export interface EmailAccount extends EmailAccountDoc {
  authKind: AuthKind;
  status: AccountStatus;
}

export interface EmailService {
  /** Email Account `service` value; `""` is a custom IMAP/SMTP account. */
  service: string;
  label: string;
  logo?: string;
  kind: "password" | "frappe-mail" | "custom";
  /** Signs in through Frappe Cloud when the site offers this provider. */
  oneClick?: OneClickProvider;
  /** Sends only, so incoming mail can't be turned on. */
  outgoingOnly?: boolean;
  help?: string;
  helpLink?: string;
}

/** The add/edit form; empty strings are fields the user left blank. */
export interface AccountForm {
  email_account_name: string;
  email_id: string;
  password: string;
  frappe_mail_site: string;
  api_key: string;
  api_secret: string;
  domain: string;
  email_server: string;
  incoming_port: string;
  smtp_server: string;
  smtp_port: string;
  use_ssl: boolean;
  use_starttls: boolean;
  use_tls: boolean;
  use_ssl_for_outgoing: boolean;
  enable_incoming: boolean;
  enable_outgoing: boolean;
}

export interface FieldError {
  field: keyof AccountForm;
  message: string;
}

export interface EmailAccountsController {
  accounts: EmailAccount[];
  loading: boolean;
  /** Why the last `load()` failed, until one succeeds. */
  error: unknown;
  /** Providers this site offers one-click sign-in for. */
  oneClickProviders: OneClickProvider[];
  load(): Promise<void>;
  create(service: EmailService, form: AccountForm): Promise<void>;
  /** Saves `changes` on `account`, then renames it when `newName` differs. */
  update(
    account: EmailAccount,
    changes: Partial<EmailAccountDoc> & { password?: string },
    newName?: string,
  ): Promise<void>;
  /** Makes `name` the default incoming/outgoing account, or clears it with `null`. */
  setDefault(kind: "incoming" | "outgoing", name: string | null): Promise<void>;
  /** Starts sign-in and leaves the page; with `emailAccount`, reconnects it. */
  connect(provider: OneClickProvider, emailAccount?: string): Promise<void>;
  pull(name: string): Promise<void>;
}
