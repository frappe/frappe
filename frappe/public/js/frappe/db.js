// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.db = {
	get_list: function (doctype, args) {
		if (!args) {
			args = {};
		}
		args.doctype = doctype;
		if (!args.fields) {
			args.fields = ["name"];
		}
		if (!("limit" in args)) {
			args.limit = 20;
		}
		return new Promise((resolve) => {
			frappe.call({
				method: "frappe.desk.reportview.get_list",
				args: args,
				type: "GET",
				callback: function (r) {
					resolve(r.message);
				},
			});
		});
	},
	exists: function (doctype, nameOrFilters) {
		return new Promise((resolve) => {
			let filters;
			if (typeof nameOrFilters === "string") {
				// may be cached and more effecient
				frappe.db.get_value(doctype, { name: nameOrFilters }, "name").then((r) => {
					r.message && r.message.name ? resolve(true) : resolve(false);
				});
			} else if (typeof nameOrFilters === "object") {
				frappe.db.count(doctype, { filters: nameOrFilters, limit: 1 }).then((count) => {
					resolve(count > 0);
				});
			}
		});
	},
	get_value: function (doctype, filters, fieldname, callback, parent_doc) {
		const fields = Array.isArray(fieldname) ? fieldname : [fieldname];
		let request;
		if (parent_doc) {
			// v2 lists have no parent doctype for child-table queries
			request = frappe.xcall(
				"frappe.client.get_value",
				{ doctype, fieldname, filters, parent: parent_doc },
				"GET"
			);
		} else if (frappe.model.is_single(doctype) || locals.DocType[doctype]?.issingle) {
			request = call_v2_api("GET", document_path(doctype, doctype), { fields });
		} else {
			request = get_first_match(doctype, filters, fields).then((row) => row || {});
		}
		return request.then((message) => {
			callback && callback(message);
			return { message };
		});
	},
	get_single_value: (doctype, field) => {
		return call_v2_api("GET", document_path(doctype, doctype), { fields: [field] }).then(
			(doc) => drop_nulls(doc)[field]
		);
	},
	set_value: function (doctype, docname, fieldname, value, callback) {
		let request;
		if (frappe.model.is_table(doctype)) {
			// v2 saves a child row on its own and returns the row, not the parent
			request = frappe.xcall("frappe.client.set_value", {
				doctype,
				name: docname,
				fieldname,
				value,
			});
		} else {
			const values =
				typeof fieldname === "object" ? fieldname : { [fieldname]: as_form_value(value) };
			request = call_v2_api("PATCH", document_path(doctype, docname), values, {
				json: true,
			});
		}
		return request.then((message) => {
			callback && callback(message);
			return { message };
		});
	},
	get_doc: function (doctype, name, filters) {
		let find_name = Promise.resolve(name || doctype);
		if (!name && filters) {
			find_name = get_first_match(doctype, filters, ["name"]).then((row) => {
				if (!row) {
					frappe.throw(__("{0} not found", [__(doctype)]));
				}
				return row.name;
			});
		}
		return find_name
			.then((docname) => call_v2_api("GET", document_path(doctype, docname)))
			.then((doc) => {
				doc = drop_nulls(doc);
				frappe.model.sync(doc);
				return doc;
			});
	},
	insert: function (doc) {
		// v2 inserts a child row on its own, without saving the parent
		if (doc.parenttype || frappe.model.is_table(doc.doctype)) {
			return frappe.xcall("frappe.client.insert", { doc });
		}
		return call_v2_api("POST", `document/${encodeURIComponent(doc.doctype)}`, doc, {
			json: true,
		});
	},
	delete_doc: function (doctype, name) {
		return call_v2_api("DELETE", document_path(doctype, name)).then(() => {
			frappe.model.delete_from_locals(doctype, name);
		});
	},
	count: function (doctype, args = {}, cache = false) {
		let filters = args.filters || {};
		let limit = args.limit;

		// has a filter with childtable?
		const distinct =
			Array.isArray(filters) &&
			filters.some((filter) => {
				return filter[0] !== doctype;
			});

		const fields = [];

		return call_v2_api(
			cache ? "GET" : "QUERY",
			`doctype/${encodeURIComponent(doctype)}/count`,
			{ filters, fields, distinct, limit },
			{ cache }
		);
	},
	get_link_options(doctype, txt = "", filters = {}, page_length = 0, include_image = false) {
		return new Promise((resolve) => {
			frappe.call({
				type: "GET",
				method: "frappe.desk.search.search_link",
				args: {
					doctype,
					txt,
					filters,
					page_length,
					include_image: include_image ? 1 : 0,
				},
				callback(r) {
					resolve(r.message);
				},
			});
		});
	},
};

function get_first_match(doctype, filters, fields) {
	if (filters !== undefined && (filters === null || typeof filters !== "object")) {
		filters = { name: filters ?? "" };
	}
	const args = { fields, limit: 1, ...(filters && { filters }) };
	return call_v2_api("GET", `document/${encodeURIComponent(doctype)}`, args).then(
		(rows) => rows[0]
	);
}

// as frappe.client.get, which returns as_dict(no_nulls=True)
function drop_nulls(doc) {
	const out = {};
	for (const [key, value] of Object.entries(doc)) {
		if (value === null) continue;
		out[key] = Array.isArray(value)
			? value.map((row) => (row && typeof row === "object" ? drop_nulls(row) : row))
			: value;
	}
	return out;
}

// as frappe.call sends a form value: objects and arrays as JSON, null and undefined as ""
function as_form_value(value) {
	if (value == null) return "";
	return $.isPlainObject(value) || Array.isArray(value) ? JSON.stringify(value) : value;
}

function document_path(doctype, name) {
	return `document/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}/`;
}

function call_v2_api(type, path, args = {}, opts = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			url: `/api/v2/${path}`,
			type,
			args,
			api_version: "v2",
			callback: (r) => resolve(r.data),
			error: (r) => reject(r?.message),
			...opts,
		});
	});
}
