import { reactive } from "vue";
import { call } from "frappe-ui";
import {
  authKind,
  markSignInStarted,
  missingDefaults,
  newAccount,
  services,
} from "./services";
import type {
  EmailAccount,
  EmailAccountDoc,
  EmailAccountsController,
} from "./types";

const FIELDS = [
  "name",
  "email_account_name",
  "email_id",
  "service",
  "auth_method",
  "connected_app",
  "connected_app.token_uri as token_uri",
  "connected_user",
  "backend_app_flow",
  "enable_incoming",
  "enable_outgoing",
  "default_incoming",
  "default_outgoing",
  "domain",
  "email_server",
  "incoming_port",
  "smtp_server",
  "smtp_port",
  "use_ssl",
  "use_starttls",
  "use_tls",
  "use_ssl_for_outgoing",
  "frappe_mail_site",
  "api_key",
];

/**
 * Data behind `EmailAccounts`: reads and writes Email Account through Frappe's own
 * methods. `doctype` is what incoming mail is appended to; `isV2Site` turns on one-click sign-in.
 */
export function useEmailAccounts(
  doctype: string,
  isV2Site = false,
): EmailAccountsController {
  let seq = 0;

  async function load() {
    const mine = ++seq;
    controller.loading = true;
    try {
      const docs = await call<EmailAccountDoc[]>("frappe.client.get_list", {
        doctype: "Email Account",
        fields: FIELDS,
        order_by: "creation desc",
        limit_page_length: 0,
      });
      const accounts = await Promise.all(
        docs.map(async (doc): Promise<EmailAccount> => {
          const hasToken =
            doc.auth_method === "OAuth" &&
            doc.connected_app &&
            !doc.backend_app_flow
              ? await call(
                  "frappe.integrations.doctype.connected_app.connected_app.has_token",
                  {
                    connected_app: doc.connected_app,
                    connected_user: doc.connected_user,
                  },
                )
              : true;
          return {
            ...doc,
            authKind: authKind(doc),
            status: hasToken ? "active" : "needs-reconnect",
          };
        }),
      );
      if (mine !== seq) return;
      controller.accounts = accounts;
      controller.error = null;
    } catch (e) {
      if (mine === seq) controller.error = e;
    } finally {
      if (mine === seq) controller.loading = false;
    }
  }

  const controller: EmailAccountsController = reactive({
    accounts: [] as EmailAccount[],
    loading: true,
    error: null,
    oneClickProviders: isV2Site ? services.flatMap((s) => s.oneClick ?? []) : [],
    load,

    async create(service, form) {
      const doc = newAccount(service, form, doctype);
      await call("frappe.client.insert", {
        doc: {
          ...doc,
          ...Object.fromEntries(
            missingDefaults(controller.accounts, doc).map((kind) => [
              `default_${kind}`,
              1,
            ]),
          ),
        },
      });
      await load();
    },

    async update(account, changes, newName) {
      try {
        if (Object.keys(changes).length) {
          await call("frappe.client.set_value", {
            doctype: "Email Account",
            name: account.name,
            fieldname: changes,
          });
        }
        if (newName && newName !== account.name) {
          await call("frappe.client.rename_doc", {
            doctype: "Email Account",
            old_name: account.name,
            new_name: newName,
          });
        }
      } finally {
        await load();
      }
    },

    async setDefault(kind, name) {
      const field = `default_${kind}` as const;
      const current = controller.accounts.find((a) => a[field])?.name ?? null;
      // making one account default un-defaults the others when it saves
      await call("frappe.client.set_value", {
        doctype: "Email Account",
        name: name ?? current,
        fieldname: field,
        value: name ? 1 : 0,
      });
      await load();
    },

    async connect(provider, emailAccount) {
      const here = new URL(window.location.href);
      here.searchParams.delete("email_oauth");
      here.searchParams.delete("email_oauth_mailbox");
      const url: string = await call(
        "frappe.integrations.frappe_providers.email_oauth.initiate_mailbox_connect",
        {
          provider,
          redirect_to: here.pathname + here.search,
          target_doctype: doctype,
          email_account: emailAccount,
        },
      );
      if (!emailAccount) markSignInStarted();
      window.location.assign(url);
    },

    async pull(name) {
      await call(
        "frappe.email.doctype.email_account.email_account.pull_emails",
        {
          email_account: name,
        },
      );
    },
  });

  return controller;
}
