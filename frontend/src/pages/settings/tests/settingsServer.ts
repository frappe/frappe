// A faked `/api/v2` for the settings tests: documents with a `modified` stamp the PATCH route
// checks, the meta route, the new-document route, and a way to hold a write in flight.
import { vi } from "vitest";

type Values = Record<string, any>;

export interface Write {
	method: string;
	path: string;
	body: Values;
}

export const SYSTEM_SETTINGS = {
	name: "System Settings",
	issingle: 1,
	fields: [
		{ fieldname: "country", fieldtype: "Data", label: "Country" },
		{ fieldname: "enable_onboarding", fieldtype: "Check", label: "Enable Onboarding" },
		{ fieldname: "time_zone", fieldtype: "Data", label: "Time Zone" },
		{ fieldname: "app_name", fieldtype: "Data", label: "App Name" },
		{ fieldname: "rules", fieldtype: "Table", label: "Rules", options: "Walk Rule" },
	],
};

export const TELEPHONY_AGENT = {
	name: "Telephony Agent",
	autoname: "field:user",
	fields: [
		{ fieldname: "user", fieldtype: "Link", label: "User", options: "User", reqd: 1 },
		{ fieldname: "mobile_no", fieldtype: "Data", label: "Mobile No" },
		{ fieldname: "extension", fieldtype: "Data", label: "Extension" },
	],
};

export const WALK_RULE = {
	name: "Walk Rule",
	istable: 1,
	fields: [{ fieldname: "rule", fieldtype: "Data", label: "Rule" }],
};

export class SettingsServer {
	readonly fetch = vi.fn<typeof fetch>();
	readonly writes: Write[] = [];
	readonly metas: Record<string, Values> = {
		"System Settings": SYSTEM_SETTINGS,
		"Telephony Agent": TELEPHONY_AGENT,
		"Walk Rule": WALK_RULE,
	};
	readonly docs = new Map<string, Values>();
	/** Each doctype's Details rows, as `get_form_layouts` sends them. */
	readonly layouts: Record<string, Values[]> = {};
	/** The `dt` of each `get_form_layouts` read. */
	readonly layoutReads: string[] = [];
	/** The next write's reply waits until this resolves. */
	held: Promise<void> | null = null;
	/** The next write is refused with this error entry and status. */
	refusal: { entry: Values; status: number } | null = null;
	private stamp = 0;

	constructor() {
		this.put("System Settings", "System Settings", {
			country: "France",
			time_zone: "Europe/Paris",
			rules: [{ name: "r1", rule: "old" }],
		});
		this.fetch.mockImplementation((url, init) => this.handle(String(url), init));
	}

	put(doctype: string, name: string, values: Values, modifiedBy = "admin@example.com") {
		const doc = { ...(this.docs.get(`${doctype}/${name}`) ?? {}), ...values };
		this.docs.set(`${doctype}/${name}`, {
			...doc,
			doctype,
			name,
			modified: this.nextStamp(),
			modified_by: modifiedBy,
		});
	}

	doc(doctype: string, name: string): Values {
		return this.docs.get(`${doctype}/${name}`)!;
	}

	private async handle(url: string, init?: RequestInit): Promise<Response> {
		const path = decodeURIComponent(new URL(url, "http://x").pathname);
		const method = init?.method ?? "GET";
		const meta = path.match(/^\/api\/v2\/doctype\/(.+)\/meta$/);
		if (meta) return json({ data: this.metas[meta[1]], children: this.children(meta[1]) });
		if (path === "/api/v2/method/frappe.desk.doctype.form_layout.form_layout.get_form_layouts") {
			const dt = new URL(url, "http://x").searchParams.get("dt")!;
			this.layoutReads.push(dt);
			return json({ data: { layouts: this.layouts[dt] ?? [], fallback: [], children: {} } });
		}
		if (path === "/api/v2/method/frappe.desk.form.load.get_new_doc")
			return json({ data: { mobile_no: "", extension: "" } });
		const [, doctype, name] = path.match(/^\/api\/v2\/document\/([^/]+)(?:\/(.+))?$/) ?? [];
		if (!doctype) return json({ errors: [{ type: "NotFound", message: path }] }, 404);
		if (method === "GET") return this.read(doctype, name);
		const body = JSON.parse(String(init!.body));
		this.writes.push({ method, path, body });
		if (this.held) await this.held;
		if (this.refusal) {
			const { entry, status } = this.refusal;
			this.refusal = null;
			return json({ errors: [entry] }, status);
		}
		return method === "POST" ? this.insert(doctype, body) : this.update(doctype, name, body);
	}

	private children(doctype: string): Values[] {
		return (this.metas[doctype]?.fields ?? [])
			.filter((field: Values) => field.fieldtype === "Table" && this.metas[field.options])
			.map((field: Values) => this.metas[field.options]);
	}

	private read(doctype: string, name: string) {
		const doc = this.docs.get(`${doctype}/${name}`);
		if (!doc) return json({ errors: [{ type: "DoesNotExistError", message: `${name} not found` }] }, 404);
		return json({ data: doc, users: { [doc.modified_by]: { full_name: "Ada Admin" } } });
	}

	private insert(doctype: string, body: Values) {
		const name = body[this.metas[doctype].autoname.slice("field:".length)];
		this.put(doctype, name, body, "reader@example.com");
		return json({ data: this.doc(doctype, name) });
	}

	private update(doctype: string, name: string, body: Values) {
		const { modified, ...values } = body;
		if (modified !== this.doc(doctype, name).modified)
			return json(
				{ errors: [{ type: "TimestampMismatchError", message: "Document has been modified" }] },
				417
			);
		this.put(doctype, name, values, "reader@example.com");
		return json({ data: this.doc(doctype, name) });
	}

	private nextStamp() {
		this.stamp += 1;
		return `2026-10-26 10:00:${String(this.stamp).padStart(2, "0")}.000000`;
	}
}

function json(body: unknown, status = 200) {
	return new Response(JSON.stringify(body), { status });
}
