// Email Account's record page: service presets, the OAuth sign-in and the account's checks.
import { Alert } from "frappe-ui";
import { getDocumentFields, runDocumentMethod, runMethod } from "@framework/ui/api";
import { __ } from "frappe/i18n";
import { IMAP_DEFAULTS, POP_DEFAULTS } from "./serviceDefaults.js";

const EMAIL_ACCOUNT = "frappe.email.doctype.email_account.email_account";
const RELAY_PREFIX = "frappe-cloud-relay:";
const GMAIL_APP_PASSWORDS =
	"https://knowledge.workspace.google.com/kb/how-to-create-app-passwords-000009237";

export default {
	onRefresh(page) {
		page.fields.hide("authorize_api_access");
		page.fields.hide("validate_frappe_mail_settings");
		describeSecrets(page);
		limitAppendTo(page);
		addSignIn(page);
		addMailCheck(page);
		addPullEmails(page);
	},
	async onOpen(page) {
		if (!page.isNew) return;
		if (!page.doc.imap_folder?.length) page.doc.imap_folder = [{ folder_name: "INBOX" }];
		if (page.doc.service) applyService(page);
		if (!page.doc.attachment_limit) {
			const size = await page.call("frappe.core.api.file.get_max_file_size");
			page.doc.attachment_limit = Number(size) / (1024 * 1024);
		}
	},
	beforeSave: (page) => moveReplyTo(page),
	service: (page) => {
		applyService(page);
		return page.refresh();
	},
	use_imap: (page) => {
		const defaults = page.doc.use_imap ? IMAP_DEFAULTS : POP_DEFAULTS;
		Object.assign(page.doc, defaults[page.doc.service]);
	},
	domain: (page) => fillFromDomain(page),
	enable_incoming: (page) => warnAutoReply(page),
	enable_auto_reply: (page) => warnAutoReply(page),
	email_sync_option: (page) => confirmSyncAll(page),
	auth_method: (page) => page.refresh(),
	connected_app: (page) => page.refresh(),
	connected_user: (page) => page.refresh(),
	backend_app_flow: (page) => page.refresh(),
};

function applyService(page) {
	Object.assign(page.doc, IMAP_DEFAULTS[page.doc.service]);
	if (!page.doc.use_imap) Object.assign(page.doc, POP_DEFAULTS[page.doc.service]);
}

function describeSecrets(page) {
	if (page.doc.service === "GMail")
		page.fields.update("password", {
			description: __("Use an app password: {0}", [GMAIL_APP_PASSWORDS]),
		});
	if (page.doc.service === "Frappe Mail")
		page.fields.update("api_secret", {
			description: __("To know more, see {0}", ["https://github.com/frappe/mail"]),
		});
}

function limitAppendTo(page) {
	const doctypes = page.cached("append_to", async () =>
		(await page.call(`${EMAIL_ACCOUNT}.get_append_to`)).map(([doctype]) => doctype)
	);
	if (doctypes) page.fields.update("append_to", { link_filters: { name: ["in", doctypes] } });
}

function addSignIn(page) {
	const { auth_method, connected_app, connected_user, backend_app_flow } = page.doc;
	if (auth_method !== "OAuth" || !connected_app || backend_app_flow) return;
	const status = page.cached(`oauth:${connected_app}:${connected_user ?? ""}`, () =>
		readSignIn(page, connected_app, connected_user)
	);
	if (!status) return;
	const signedOut = status.relay && !status.hasToken;
	if (!status.hasToken) addSignInBand(page, signedOut);
	if (!connected_user && !signedOut) return;
	page.header.add(
		{
			name: "authorize_api_access",
			label: signedOut ? __("Reconnect") : __("Authorize API Access"),
			display: "button",
			// A new record has no record rights before its insert, which checks create.
			right: page.isNew ? undefined : "write",
			run: (page) => authorize(page, status.relay),
		},
		{ before: "save" }
	);
}

async function readSignIn(page, connectedApp, connectedUser) {
	const [hasToken, app] = await Promise.all([
		page.call("frappe.integrations.doctype.connected_app.connected_app.has_token", {
			connected_app: connectedApp,
			connected_user: connectedUser,
		}),
		getDocumentFields("Connected App", connectedApp, ["token_uri"]),
	]);
	const tokenUri = app.data?.token_uri ?? "";
	return { hasToken: Boolean(hasToken), relay: tokenUri.startsWith(RELAY_PREFIX) };
}

function addSignInBand(page, signedOut) {
	const title = signedOut
		? __("This mailbox was signed out. Reconnect it to sign in again.")
		: __('OAuth has been enabled but not authorised. Use "Authorize API Access" to do so.');
	page.frame.add(
		{ name: "oauth_status", component: Alert, props: { theme: "amber", title } },
		{ after: "header" }
	);
}

async function authorize(page, relay) {
	const reply = relay
		? await runMethod(
				"frappe.integrations.frappe_providers.email_oauth.initiate_mailbox_connect",
				{ email_account: page.docname },
				{ nullable: true }
		  )
		: await runDocumentMethod(
				"Connected App",
				page.doc.connected_app,
				"initiate_web_application_flow",
				{ success_uri: window.location.pathname, user: page.doc.connected_user }
		  );
	if (reply.data) window.location.href = reply.data;
}

function addMailCheck(page) {
	const { service, auth_method } = page.doc;
	if (service !== "Frappe Mail" || auth_method === "Basic" || page.isNew || page.isDirty) return;
	page.header.add(
		{
			name: "validate_frappe_mail_settings",
			label: __("Validate Frappe Mail Settings"),
			display: "button",
			right: "write",
			run: async (page) => {
				await runDocumentMethod(
					"Email Account",
					page.docname,
					"validate_frappe_mail_settings",
					{},
					{ nullable: true }
				);
				page.toast.success(__("Frappe Mail settings are valid"));
			},
		},
		{ before: "save" }
	);
}

function addPullEmails(page) {
	if (page.isNew || page.isDirty || !page.doc.enable_incoming) return;
	page.header.add(
		{
			name: "pull_emails",
			label: __("Pull Emails"),
			display: "button",
			right: "read",
			run: async (page) => {
				await runMethod(
					`${EMAIL_ACCOUNT}.pull_emails`,
					{ email_account: page.docname },
					{ nullable: true }
				);
				page.toast.success(__("Emails Pulled"));
			},
		},
		{ before: "save" }
	);
}

async function fillFromDomain(page) {
	if (!page.doc.domain) return;
	const values = await page.call("run_doc_method", {
		method: "get_domain_values",
		// The server tells a new document by `__islocal`, as desk v1 sends it.
		document: { ...page.doc, doctype: page.doctype, __islocal: page.isNew ? 1 : 0 },
		kwargs: { domain: page.doc.domain },
	});
	Object.assign(page.doc, values);
}

async function warnAutoReply(page) {
	if (!page.isNew || !page.doc.enable_incoming || !page.doc.enable_auto_reply) return;
	const confirmed = await page.dialog.confirm({
		title: __("Enable auto reply?"),
		message: __(
			"Enabling auto reply on an incoming email account will send automated replies to all the synchronized emails. Do you wish to continue?"
		),
	});
	if (confirmed) return;
	page.doc.enable_auto_reply = 0;
	page.toast.success(__("Disabled Auto Reply"));
}

async function confirmSyncAll(page) {
	if (page.doc.email_sync_option !== "ALL") return;
	const confirmed = await page.dialog.confirm({
		title: __("Sync all emails?"),
		message: __(
			"You are selecting Sync Option as ALL, It will resync all read as well as unread message from server. This may also cause the duplication of Communication (emails)."
		),
	});
	if (!confirmed) page.doc.email_sync_option = "UNSEEN";
}

async function moveReplyTo(page) {
	const previous = page.saved.email_id;
	const current = page.doc.email_id;
	if (!previous || !current || previous === current) return;
	const stale = page
		.rows("reply_to_addresses")
		.filter((row) => row.email?.toLowerCase() === previous.toLowerCase());
	if (!stale.length) return;
	const confirmed = await page.dialog.confirm({
		title: __("Update Reply-To Addresses?"),
		message: __("Reply-To Addresses still include {0}. Change it to {1} as well?", [
			previous,
			current,
		]),
	});
	if (confirmed) for (const row of stale) row.email = current;
}
