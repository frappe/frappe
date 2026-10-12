import { expect } from "@playwright/test";

export class Api {
	constructor(request, page = null) {
		this.request = request;
		this.page = page;
		this.token = null;
	}

	async headers() {
		const token = await this.page
			?.evaluate(() => window.frappe && window.frappe.csrf_token)
			.catch(() => null);
		if (token && token !== "None") {
			this.token = token;
		}
		const headers = { Accept: "application/json" };
		if (this.token) {
			headers["X-Frappe-CSRF-Token"] = this.token;
		}
		return headers;
	}

	async call(method, args = {}) {
		const res = await this.request.post(`/api/method/${method}`, {
			data: args,
			headers: await this.headers(),
		});
		expect(res.status(), `${method}: ${await res.text()}`).toBe(200);
		return await res.json();
	}

	async get_list(doctype, fields = [], filters = []) {
		const res = await this.request.get(`/api/resource/${doctype}`, {
			params: { fields: JSON.stringify(fields), filters: JSON.stringify(filters) },
			headers: await this.headers(),
		});
		expect(res.status()).toBe(200);
		return await res.json();
	}

	async get_doc(doctype, name) {
		const res = await this.request.get(`/api/resource/${doctype}/${name}`, {
			headers: await this.headers(),
		});
		expect(res.status()).toBe(200);
		return await res.json();
	}

	async insert_doc(doctype, args, ignore_duplicate = false) {
		const res = await this.request.post(`/api/resource/${doctype}`, {
			data: { doctype, ...args },
			headers: await this.headers(),
		});
		const allowed = ignore_duplicate ? [200, 409] : [200];
		expect(allowed, `insert ${doctype}: ${await res.text()}`).toContain(res.status());
		return (await res.json()).data;
	}

	async update_doc(doctype, name, args) {
		const res = await this.request.put(`/api/resource/${doctype}/${name}`, {
			data: args,
			headers: await this.headers(),
		});
		expect(res.status(), `update ${doctype}: ${await res.text()}`).toBe(200);
		return (await res.json()).data;
	}

	async remove_doc(doctype, name, ignore_missing = false) {
		const res = await this.request.delete(`/api/resource/${doctype}/${name}`, {
			headers: await this.headers(),
		});
		if (!(ignore_missing && res.status() === 404)) {
			expect(res.ok(), `delete ${doctype}: ${await res.text()}`).toBeTruthy();
		}
		return await res.json().catch(() => null);
	}

	async create_records(doc) {
		const r = await this.call("frappe.tests.ui_test_helpers.create_if_not_exists", {
			doc: JSON.stringify(doc),
		});
		return r.message;
	}

	set_value(doctype, name, values) {
		return this.call("frappe.client.set_value", { doctype, name, fieldname: values });
	}
}
