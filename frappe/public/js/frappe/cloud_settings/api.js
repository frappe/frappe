const METHOD_PREFIX = "frappe.integrations.frappe_providers.cloud_settings";

// Cloud Settings shows errors inline in the dialog, so we suppress frappe's
// automatic message toast (`silent`) and reject with the server's message.
function call(method, args = {}, type = "POST") {
	return new Promise((resolve, reject) => {
		const request = frappe.call({
			method: `${METHOD_PREFIX}.${method}`,
			args,
			type,
			silent: true,
			callback: (response) => resolve(response.message),
			error: (response) => reject(new Error(messageFromResponse(response))),
		});
		// frappe.call also returns a promise; swallow its rejection so the error
		// we already handle above doesn't surface as an unhandled rejection.
		Promise.resolve(request).catch(() => {});
	});
}

// Pull the human-readable message out of a frappe error response.
function messageFromResponse(response) {
	const raw = response?._server_messages || response?.responseJSON?._server_messages;
	if (raw) {
		try {
			const messages = JSON.parse(raw)
				.map((item) => JSON.parse(item).message)
				.filter(Boolean);
			if (messages.length) return messages.join(". ").replace(/<[^>]*>/g, "");
		} catch {
			// fall through to the generic message
		}
	}
	return __("Something went wrong. Please try again.");
}

export function getContext() {
	return call("get_context", {}, "GET");
}

export function getBilling() {
	return call("get_billing", {}, "GET");
}

export function getBillingProfile() {
	return call("get_billing_profile", {}, "GET");
}

export function saveBillingProfile(fields) {
	return call("save_billing_profile", fields);
}

export function removePaymentMethod(name) {
	return call("remove_payment_method", { payment_method: name });
}

export function getPaymentGateways() {
	return call("get_payment_gateways", {}, "GET");
}

export function addPaymentMethod(methodType, gateway, contact) {
	return call("add_payment_method", { method_type: methodType, gateway, contact });
}

export function confirmPaymentMethod(payload) {
	return call("confirm_payment_method", payload);
}

export function createPaymentMethodCheckout(gateway) {
	return call("create_payment_method_checkout", { gateway });
}

export function confirmPaymentMethodCheckout(reference) {
	return call("confirm_payment_method_checkout", { reference });
}

export function reconcilePaymentSetup() {
	return call("reconcile_payment_setup", {});
}

export function createTopupCheckout(amount) {
	return call("create_topup_checkout", { amount });
}

export function getCheckoutStatus(reference) {
	return call("get_checkout_status", { reference });
}

export function getMarketplaceApps() {
	return call("get_marketplace_apps", {}, "GET");
}

export function installApp(app) {
	return call("install_app", { app });
}

export function uninstallApp(app) {
	return call("uninstall_app", { app });
}

export function updateApps(apps) {
	return call("update_apps", apps ? { apps: JSON.stringify(apps) } : {});
}

export function getTask(taskId) {
	return call("get_task", { task_id: taskId }, "GET");
}

export function getDomains() {
	return call("get_domains", {}, "GET");
}

export function getDomainDnsRecords(domain) {
	return call("get_domain_dns_records", { domain });
}

export function addDomain(domain) {
	return call("add_domain", { domain });
}

export function removeDomain(domain) {
	return call("remove_domain", { domain });
}

export function setPrimaryDomain(domain) {
	return call("set_primary_domain", { domain });
}

export function getErrorMessage(exception, fallback) {
	// call() rejects with an Error already carrying the server's message.
	return exception?.message || fallback || __("Something went wrong.");
}
