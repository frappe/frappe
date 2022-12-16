// REDESIGN-TODO: Review

function get_version_timeline_content(version_doc, frm) {
	if (!version_doc.data) return [];
	const data = JSON.parse(version_doc.data);

	// comment
	if (data.comment) {
		return [get_version_comment(version_doc, data.comment)];
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
		var parts = [];
		data.changed.every(function (p) {
			if (p[0] === "docstatus") {
				if (p[2] === 1) {
					let message = updater_reference_link
						? __("{0} submitted this document {1}", [
								get_user_link(version_doc),
								updater_reference_link,
						  ])
						: __("{0} submitted this document", [get_user_link(version_doc)]);
					out.push(get_version_comment(version_doc, message));
				} else if (p[2] === 2) {
					let message = updater_reference_link
						? __("{0} cancelled this document {1}", [
								get_user_link(version_doc),
								updater_reference_link,
						  ])
						: __("{0} cancelled this document", [get_user_link(version_doc)]);
					out.push(get_version_comment(version_doc, message));
				}
			} else {
				const df = frappe.meta.get_docfield(frm.doctype, p[0], frm.docname);
				if (df && !df.hidden) {
					const field_display_status = frappe.perm.get_field_display_status(
						df,
						null,
						frm.perm
					);
					if (field_display_status === "Read" || field_display_status === "Write") {
						parts.push(
							__("{0} from {1} to {2}", [
								__(df.label),
								format_content_for_timeline(p[1]),
								format_content_for_timeline(p[2]),
							])
						);
					}
				}
			}
			return parts.length < 3;
		});
		if (parts.length) {
			let message;
			if (updater_reference_link) {
				message = __("{0} changed value of {1} {2}", [
					get_user_link(version_doc),
					parts.join(", "),
					updater_reference_link,
				]);
			} else {
				message = __("{0} changed value of {1}", [
					get_user_link(version_doc),
					parts.join(", "),
				]);
			}
			out.push(get_version_comment(version_doc, message));
		}
	}

	// value changed in table field
	if (data.row_changed && data.row_changed.length) {
		let parts = [];
		data.row_changed.every(function (row) {
			row[3].every(function (p) {
				var df =
					frm.fields_dict[row[0]] &&
					frappe.meta.get_docfield(
						frm.fields_dict[row[0]].grid.doctype,
						p[0],
						frm.docname
					);

				if (df && !df.hidden) {
					var field_display_status = frappe.perm.get_field_display_status(
						df,
						null,
						frm.perm
					);

					if (field_display_status === "Read" || field_display_status === "Write") {
						parts.push(
							__("{0} from {1} to {2} in row #{3}", [
								frappe.meta.get_label(frm.fields_dict[row[0]].grid.doctype, p[0]),
								format_content_for_timeline(p[1]),
								format_content_for_timeline(p[2]),
								row[1],
							])
						);
					}
				}
				return parts.length < 3;
			});
			return parts.length < 3;
		});
		if (parts.length) {
			let message;
			if (updater_reference_link) {
				message = __("{0} changed values for {1} {2}", [
					get_user_link(version_doc),
					parts.join(", "),
					updater_reference_link,
				]);
			} else {
				message = __("{0} changed values for {1}", [
					get_user_link(version_doc),
					parts.join(", "),
				]);
			}
			out.push(get_version_comment(version_doc, message));
		}
	}

	// rows added / removed
	// __('added'), __('removed') # for translation, don't remove
	["added", "removed"].forEach(function (key) {
		if (data[key] && data[key].length) {
			let parts = (data[key] || []).map(function (p) {
				var df = frappe.meta.get_docfield(frm.doctype, p[0], frm.docname);
				if (df && !df.hidden) {
					var field_display_status = frappe.perm.get_field_display_status(
						df,
						null,
						frm.perm
					);

					if (field_display_status === "Read" || field_display_status === "Write") {
						return __(frappe.meta.get_label(frm.doctype, p[0]));
					}
				}
			});
			parts = parts.filter(function (p) {
				return p;
			});
			if (parts.length) {
				let message = "";

				if (key === "added") {
					message = __("added rows for {0}", [parts.join(", ")]);
				} else if (key === "removed") {
					message = __("removed rows for {0}", [parts.join(", ")]);
				}

				let version_comment = get_version_comment(version_doc, message);
				let user_link = get_user_link(version_doc);
				out.push(`${user_link} ${version_comment}`);
			}
		}
	});

	return out;
}

function get_version_comment(version_doc, text) {
	// TODO: Replace with a better solution
	if (text.includes("<a")) {
		// if text already has linked content in it
		// then just add a version link to unlinked content
		let version_comment = "";
		let unlinked_content = "";

		try {
			text += "</>";
			Array.from($(text)).forEach((element) => {
				if ($(element).is("a")) {
					version_comment += unlinked_content
						? frappe.utils.get_form_link(
								"Version",
								version_doc.name,
								true,
								unlinked_content
						  )
						: "";
					unlinked_content = "";
					version_comment += element.outerHTML;
				} else {
					unlinked_content += element.outerHTML || element.textContent;
				}
			});
			if (unlinked_content) {
				version_comment += frappe.utils.get_form_link(
					"Version",
					version_doc.name,
					true,
					unlinked_content
				);
			}
			return version_comment;
		} catch (e) {
			// pass
		}
	}
	return frappe.utils.get_form_link("Version", version_doc.name, true, text);
}

function format_content_for_timeline(content) {
	// text to HTML
	// limits content to 40 characters
	// escapes HTML
	// and makes it bold
	content = frappe.ellipsis(content, 40) || '""';
	content = frappe.utils.escape_html(content);
	return content.bold();
}

function get_user_link(doc) {
	const user = doc.owner;
	const user_display_text = (frappe.user_info(user).fullname || "").bold();
	return frappe.utils.get_form_link("User", user, true, user_display_text);
}

export { get_version_timeline_content };
