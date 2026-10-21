function get_version_timeline_content(version_doc, frm) {
	if (!version_doc.data) return [];
	const data = JSON.parse(version_doc.data);

	// comment
	if (data.comment) {
		return [data.comment];
	}

	let out = [];

	let updater_reference_link = null;
	let updater_reference = data.updater_reference;
	if (!$.isEmptyObject(updater_reference)) {
		let label = updater_reference.label || __("via {0}", [updater_reference.doctype]);
		let { doctype, docname } = updater_reference;
		if (doctype && docname) {
			updater_reference_link = frappe.utils.get_form_link(doctype, docname, true, label);
		} else {
			updater_reference_link = label;
		}
	}

	// value changed in parent
	if (data.changed && data.changed.length) {
		data.changed.every(function (p) {
			if (p[0] === "docstatus") {
				if (p[2] === 1) {
					let message = updater_reference_link
						? get_user_message(
								version_doc.owner,
								__(
									"You submitted this document {0}",
									[updater_reference_link],
									"Form timeline"
								),
								__(
									"{0} submitted this document {1}",
									[get_user_link(version_doc.owner), updater_reference_link],
									"Form timeline"
								)
						  )
						: get_user_message(
								version_doc.owner,
								__("You submitted this document", null, "Form timeline"),
								__(
									"{0} submitted this document",
									[get_user_link(version_doc.owner)],
									"Form timeline"
								)
						  );

					out.push(message);
				} else if (p[2] === 2) {
					let message = updater_reference_link
						? get_user_message(
								version_doc.owner,
								__(
									"You cancelled this document {0}",
									[updater_reference_link],
									"Form timeline"
								),
								__(
									"{0} cancelled this document {1}",
									[get_user_link(version_doc.owner), updater_reference_link],
									"Form timeline"
								)
						  )
						: get_user_message(
								version_doc.owner,
								__("You cancelled this document", null, "Form timeline"),
								__(
									"{0} cancelled this document",
									[get_user_link(version_doc.owner)],
									"Form timeline"
								)
						  );

					out.push(message);
				}
			}
			return true;
		});
		const changes = get_changed_fields(data, frm);
		if (changes.length) {
			out.push(get_field_changes_comment(version_doc, changes, updater_reference_link));
		}
	}

	// value changed in table field
	const row_changes = get_changed_row_fields(data, frm);
	if (row_changes.length) {
		out.push(get_field_changes_comment(version_doc, row_changes, updater_reference_link));
	}

	// rows added / removed
	["added", "removed"].forEach((key) => {
		const tables = get_rows_by_table(data[key], frm);
		if (!tables.length) return;
		const messages = tables.map((table, i) =>
			get_rows_message(key, table, version_doc, i === 0)
		);
		const { toggle, body } = get_rows_details(tables, version_doc);
		out.push({ summary: frappe.utils.comma_and(messages), toggle, details: body });
	});

	if (data.created_by && updater_reference) {
		let message = get_user_message(
			version_doc.owner,
			__("You created this document {0}", [updater_reference_link], "Form timeline"),
			__(
				"{0} created this document {1}",
				[get_user_link(version_doc.owner), updater_reference_link],
				"Form timeline"
			)
		);
		out.push(message);
	}
	const impersonated_by = data.impersonated_by;

	// field changes carry a details block which must stay after the suffixes
	out = out.map((message) => (typeof message === "string" ? { summary: message } : message));

	if (impersonated_by) {
		const impersonated_msg = __("Impersonated by {0}", [get_user_link(impersonated_by)]);
		out.forEach((message) => (message.summary += ` · ${impersonated_msg.bold()}`));
	}

	const audit_user = data.audit_user;
	if (audit_user) {
		const audit_msg = __("[Action taken by {0}]", [audit_user]);
		out.forEach((message) => (message.summary += ` · ${audit_msg.bold()}`));
	}
	return out.map(
		(message) => message.summary + (message.toggle || "") + (message.details || "")
	);
}

function is_visible_on_timeline(df, frm) {
	if (!df || (df.hidden && !df.show_on_timeline)) return false;
	const status = frappe.perm.get_field_display_status(df, null, frm.perm);
	return status === "Read" || status === "Write" || (df.hidden && df.show_on_timeline);
}

function get_changed_fields(data, frm) {
	return (data.changed || [])
		.filter((p) => p[0] !== "docstatus")
		.map((p) => [frappe.meta.get_docfield(frm.doctype, p[0], frm.docname), p])
		.filter(([df]) => is_visible_on_timeline(df, frm))
		.map(([df, p]) => ({
			label: __(df.label, null, df.parent),
			old_value: get_check_value(p[1], df),
			new_value: get_check_value(p[2], df),
		}));
}

function get_changed_row_fields(data, frm) {
	const changes = [];
	(data.row_changed || []).forEach((row) => {
		const grid_doctype = frm.fields_dict[row[0]]?.df?.options;
		if (!grid_doctype) return;
		row[3].forEach((p) => {
			const df = frappe.meta.get_docfield(grid_doctype, p[0], frm.docname);
			if (!is_visible_on_timeline(df, frm)) return;
			const current_row = (frm.doc[row[0]] || []).find((d) => d.name === row[2]);
			const row_title = current_row && get_row_title(grid_doctype, current_row);
			const field_label = frappe.meta.get_translated_label(grid_doctype, p[0]);
			changes.push({
				label: row_title
					? __("{0} for {1}", [field_label, row_title], "Form timeline")
					: __("{0} in row #{1}", [field_label, row[1] + 1]),
				old_value: get_check_value(p[1], df),
				new_value: get_check_value(p[2], df),
			});
		});
	});
	return changes;
}

// values are cut off visually with a tooltip; this only bounds the markup
const MAX_VALUE_LENGTH = 300;

function get_field_changes_comment(version_doc, changes, updater_reference_link) {
	const user_link = get_user_link(version_doc.owner);
	const suffix = updater_reference_link ? ` ${updater_reference_link}` : "";

	if (changes.length === 1) {
		const { label, old_value, new_value } = changes[0];
		const field = get_version_link(version_doc, frappe.utils.escape_html(label));
		const diff = get_value_diff(old_value, new_value);
		const message = get_user_message(
			version_doc.owner,
			__("You changed {0} from {1}", [field, diff], "Form timeline"),
			__("{0} changed {1} from {2}", [user_link, field, diff], "Form timeline")
		);
		return { summary: message + suffix };
	}

	const count = get_version_link(
		version_doc,
		__("{0} fields", [changes.length], "Form timeline")
	);
	const message = get_user_message(
		version_doc.owner,
		__("You changed {0}", [count], "Form timeline"),
		__("{0} changed {1}", [user_link, count], "Form timeline")
	);
	const rows = changes
		.map(
			({ label, old_value, new_value }, i) => `
			<div class="timeline-change-row${i >= CHANGES_PREVIEW ? " timeline-change-more" : ""}">
				<span class="timeline-change-label">${get_version_link(
					version_doc,
					frappe.utils.escape_html(label)
				)}</span>
				${get_value_diff(old_value, new_value)}
			</div>`
		)
		.join("");
	const show_all =
		changes.length > CHANGES_PREVIEW
			? frappe.ui.button.html({
					label: __("Show all changes", null, "Form timeline"),
					icon_right: "chevron-down",
					css_class: "timeline-changes-more-toggle",
					attrs: {
						"aria-expanded": "false",
						"data-show-label": __("Show all changes", null, "Form timeline"),
						"data-hide-label": __("Show fewer", null, "Form timeline"),
					},
			  })
			: "";
	return {
		summary: message + suffix,
		details: `
			<div class="timeline-changes">
				<div class="timeline-changes-grid">${rows}</div>
				${show_all}
			</div>`,
	};
}

const CHANGES_PREVIEW = 5;

function get_version_link(version_doc, html) {
	const href = frappe.utils.get_form_link("Version", version_doc.name);
	return `<a class="timeline-version-link" href="${href}">${html}</a>`;
}

function get_rows_by_table(rows, frm) {
	const tables = [];
	(rows || []).forEach(([fieldname, row]) => {
		const table_df = frappe.meta.get_docfield(frm.doctype, fieldname, frm.docname);
		if (!is_visible_on_timeline(table_df, frm)) return;
		let table = tables.find((t) => t.fieldname === fieldname);
		if (!table) {
			table = {
				fieldname,
				doctype: table_df.options,
				label: frappe.utils.escape_html(__(table_df.label, null, table_df.parent)),
				rows: [],
			};
			tables.push(table);
		}
		table.rows.push(row);
	});
	return tables;
}

function get_row_title_field(doctype) {
	const fields = (frappe.get_meta(doctype)?.fields || []).filter(
		(df) => df.in_list_view && !frappe.model.no_value_type.includes(df.fieldtype)
	);
	return fields.find(
		(df) => !["Check", "Currency", "Float", "Int", "Percent"].includes(df.fieldtype)
	);
}

function get_row_title(doctype, row) {
	const df = get_row_title_field(doctype);
	const value = df && row[df.fieldname];
	if (value == null || value === "") return "";
	return get_display_value(value, df, row);
}

function get_rows_message(key, table, version_doc, first) {
	const count = table.rows.length;
	const row_title = get_row_title(table.doctype, table.rows[0]);
	const owner = first && version_doc.owner;
	const title = row_title && get_version_link(version_doc, frappe.utils.escape_html(row_title));
	const user_link = owner && get_user_link(owner);
	const label = title ? table.label : get_version_link(version_doc, table.label);
	const added = key === "added";
	let self, other, rest;
	if (title && count === 1) {
		self = added
			? __("You added {0} to {1}", [title, label])
			: __("You removed {0} from {1}", [title, label]);
		other = added
			? __("{0} added {1} to {2}", [user_link, title, label])
			: __("{0} removed {1} from {2}", [user_link, title, label]);
		rest = added ? __("{0} to {1}", [title, label]) : __("{0} from {1}", [title, label]);
	} else if (title) {
		const more = count - 1;
		self = added
			? __("You added {0} and {1} more to {2}", [title, more, label])
			: __("You removed {0} and {1} more from {2}", [title, more, label]);
		other = added
			? __("{0} added {1} and {2} more to {3}", [user_link, title, more, label])
			: __("{0} removed {1} and {2} more from {3}", [user_link, title, more, label]);
		rest = added
			? __("{0} and {1} more to {2}", [title, more, label])
			: __("{0} and {1} more from {2}", [title, more, label]);
	} else if (count === 1) {
		self = added
			? __("You added 1 row to {0}", [label])
			: __("You removed 1 row from {0}", [label]);
		other = added
			? __("{0} added 1 row to {1}", [user_link, label])
			: __("{0} removed 1 row from {1}", [user_link, label]);
		rest = added
			? __("1 row to {0}", [label], "User added row to child table")
			: __("1 row from {0}", [label], "User removed row from child table");
	} else {
		self = added
			? __("You added {0} rows to {1}", [count, label])
			: __("You removed {0} rows from {1}", [count, label]);
		other = added
			? __("{0} added {1} rows to {2}", [user_link, count, label])
			: __("{0} removed {1} rows from {2}", [user_link, count, label]);
		rest = added
			? __("{0} rows to {1}", [count, label], "User added rows to child table")
			: __("{0} rows from {1}", [count, label], "User removed rows from child table");
	}
	return owner ? get_user_message(owner, self, other) : rest;
}

function get_rows_details(tables, version_doc) {
	const several = tables.length > 1 || tables[0].rows.length > 1;
	const blocks = tables
		.flatMap((table) => {
			const title_df = get_row_title_field(table.doctype);
			const fields = (frappe.get_meta(table.doctype)?.fields || []).filter(
				(df) =>
					df.in_list_view &&
					!frappe.model.no_value_type.includes(df.fieldtype) &&
					!(title_df && df.fieldname === title_df.fieldname && !several)
			);
			return table.rows.map((row) => {
				const values = fields
					.filter((df) => !is_empty_value(row[df.fieldname]))
					.slice(0, 4)
					.map(
						(df) => `<span class="timeline-change-label">${get_version_link(
							version_doc,
							frappe.utils.escape_html(__(df.label, null, df.parent))
						)}</span>
						<span class="timeline-row-value">${format_value_for_timeline(
							get_display_value(row[df.fieldname], df, row)
						)}</span>`
					)
					.join("");
				if (!values) return "";
				const title = several
					? `<div class="timeline-row-title">${
							frappe.utils.escape_html(get_row_title(table.doctype, row)) ||
							__("{0}, row #{1}", [table.label, row.idx])
					  }</div>`
					: "";
				return `<div class="timeline-row">${title}<div class="timeline-row-fields">${values}</div></div>`;
			});
		})
		.join("");
	if (!blocks) return {};

	return {
		toggle: frappe.ui.button.html({
			label: __("Show"),
			icon_right: "chevron-down",
			variant: "ghost",
			size: "xs",
			css_class: "timeline-changes-toggle",
			attrs: { "aria-expanded": "false" },
		}),
		body: `<div class="timeline-changes" hidden>
			<div class="timeline-rows">${blocks}</div>
		</div>`,
	};
}

function get_check_value(value, df) {
	return df.fieldtype === "Check" ? get_display_value(value, df) : value;
}

function is_empty_value(value) {
	// an unticked box still reads No; only a value never set is left out
	return value == null || value === "";
}

function get_display_value(value, df, row) {
	if (df.fieldtype === "Check") return cint(value) ? __("Yes") : __("No");
	return frappe.utils.html2text(frappe.format(value, df, { inline: true }, row));
}

function get_value_diff(old_value, new_value) {
	return `<span class="timeline-change">
		<span class="timeline-change-old">${format_value_for_timeline(old_value)}</span>
		${frappe.utils.icon("arrow-right", "xs")}
		<span class="timeline-change-new">${format_value_for_timeline(new_value)}</span>
	</span>`;
}

function format_value_for_timeline(content) {
	// text to HTML
	// escapes HTML
	if (content == null) content = "";
	const html = String(content);
	content = frappe.utils.html2text(html);
	if (!content.trim() && /<(img|table|video|iframe)\b/i.test(html)) {
		content = /<img\b/i.test(html)
			? __("(image)", null, "Form timeline")
			: __("(rich text)", null, "Form timeline");
	}
	content = frappe.ellipsis(content, MAX_VALUE_LENGTH);
	if (!content) {
		return `<span class="timeline-empty-value">${__("empty", null, "Form timeline")}</span>`;
	}
	return frappe.utils.escape_html(content);
}

function get_user_link(user) {
	const user_display_text = frappe.user_info(user).fullname || "";
	return frappe.utils.get_form_link(
		"User",
		user,
		true,
		frappe.utils.xss_sanitise(user_display_text)
	);
}

function get_user_message(user, message_self, message_other) {
	if (!frappe.utils.is_current_user(user)) {
		return message_other;
	}
	// highlight "You" only when the translation starts with it
	const you = __("You");
	const rest = message_self.slice(you.length);
	if (message_self.startsWith(you) && /^\s/.test(rest)) {
		return `<span class="timeline-you">${you}</span>${rest}`;
	}
	return message_self;
}

export { get_version_timeline_content, get_user_link, get_user_message };
