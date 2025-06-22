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

					out.push(get_version_comment(version_doc, message));
				} else if (p[2] === 2) {
					let message = updater_reference_link
						? get_user_message(
								version_doc.owner,
								__(
									"You cancelled this document {1}",
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

					out.push(get_version_comment(version_doc, message));
				}
			} else {
				const df = frappe.meta.get_docfield(frm.doctype, p[0], frm.docname);
				if (df && (!df.hidden || df.show_on_timeline)) {
					const field_display_status = frappe.perm.get_field_display_status(
						df,
						null,
						frm.perm
					);
					if (
						field_display_status === "Read" ||
						field_display_status === "Write" ||
						(df.hidden && df.show_on_timeline)
					) {
						parts.push(
							__("{0} from {1} to {2}", [
								__(df.label, null, df.parent),
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
			let message = updater_reference_link
				? get_user_message(
						version_doc.owner,
						__("You changed the value of {0} {1}", [
							parts.join(", "),
							updater_reference_link,
						]),
						__("{0} changed the value of {1} {2}", [
							get_user_link(version_doc.owner),
							parts.join(", "),
							updater_reference_link,
						])
				  )
				: get_user_message(
						version_doc.owner,
						__("You changed the value of {0}", [parts.join(", ")]),
						__("{0} changed the value of {1}", [
							get_user_link(version_doc.owner),
							parts.join(", "),
						])
				  );

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

				if (df && (!df.hidden || df.show_on_timeline)) {
					var field_display_status = frappe.perm.get_field_display_status(
						df,
						null,
						frm.perm
					);

					if (
						field_display_status === "Read" ||
						field_display_status === "Write" ||
						(df.hidden && df.show_on_timeline)
					) {
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
			let message = updater_reference_link
				? get_user_message(
						version_doc.owner,
						__("You changed the values for {0} {1}", [
							parts.join(", "),
							updater_reference_link,
						]),
						__("{0} changed the values for {1} {2}", [
							get_user_link(version_doc.owner),
							parts.join(", "),
							updater_reference_link,
						])
				  )
				: get_user_message(
						version_doc.owner,
						__("You changed the values for {0}", [parts.join(", ")]),
						__("{0} changed the values for {1}", [
							get_user_link(version_doc.owner),
							parts.join(", "),
						])
				  );

			out.push(get_version_comment(version_doc, message));
		}
	}

	// rows added / removed
	// __('added'), __('removed') # for translation, don't remove
	["added", "removed"].forEach(function (key) {
		if (data[key] && data[key].length) {
			let parts = (data[key] || []).map(function (p) {
				var df = frappe.meta.get_docfield(frm.doctype, p[0], frm.docname);

				if (df && (!df.hidden || df.show_on_timeline)) {
					var field_display_status = frappe.perm.get_field_display_status(
						df,
						null,
						frm.perm
					);

					if (
						field_display_status === "Read" ||
						field_display_status === "Write" ||
						(df.hidden && df.show_on_timeline)
					) {
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
				let user_link = get_user_link(version_doc.owner);
				out.push(`${user_link} ${version_comment}`);
			}
		}
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
		out.push(get_version_comment(version_doc, message));
	}
	const impersonated_by = data.impersonated_by;

	if (impersonated_by) {
		const impersonated_msg = __("Impersonated by {0}", [get_user_link(impersonated_by)]);
		out = out.map((message) => `${message} · ${impersonated_msg.bold()}`);
	}

	const audit_user = data.audit_user;
	if (audit_user) {
		const audit_msg = __("[Action taken by {0}]", [audit_user]);
		out = out.map((message) => `${message} · ${audit_msg.bold()}`);
	}
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
	content = frappe.utils.html2text(content);
	content = frappe.ellipsis(content, 40) || '""';
	content = frappe.utils.escape_html(content);
	return content.bold();
}

function get_user_link(user) {
	const user_display_text = frappe.user_info(user).fullname || "";
	return frappe.utils.get_form_link("User", user, true, user_display_text);
}

function get_user_message(user, message_self, message_other) {
	return frappe.utils.is_current_user(user) ? message_self : message_other;
}

export { get_version_timeline_content, get_user_link, get_user_message };
