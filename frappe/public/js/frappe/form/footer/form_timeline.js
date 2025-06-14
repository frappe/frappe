// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import BaseTimeline from "./base_timeline";
import {
	get_version_timeline_content,
	get_user_link,
	get_user_message,
} from "./version_timeline_content_builder";

class FormTimeline extends BaseTimeline {
	make() {
		super.make();
		this.setup_timeline_actions();
		this.render_timeline_items();
		this.setup_activity_toggle();
	}

	refresh() {
		super.refresh();
		this.frm.trigger("timeline_refresh");
		this.setup_document_email_link();
	}

	setup_timeline_actions() {
		if (frappe.model.can_email(null, this.frm)) {
			this.add_action_button(
				__("New Email"),
				() => this.compose_mail(),
				"es-line-add",
				"btn-secondary"
			);
		}
		this.setup_new_event_button();
	}

	setup_new_event_button() {
		if (this.frm.meta.allow_events_in_timeline) {
			let create_event = () => {
				const args = {
					doc: this.frm.doc,
					frm: this.frm,
					recipients: this.get_recipient(),
					txt: frappe.markdown(this.frm.comment_box.get_value()),
				};
				return new frappe.views.InteractionComposer(args);
			};
			this.add_action_button(__("New Event"), create_event, "calendar");
		}
	}

	setup_activity_toggle() {
		let doc_info = this.doc_info || this.frm.get_docinfo();
		let has_communications = () => {
			let communications = doc_info.communications;
			let comments = doc_info.comments;
			return (communications || []).length || (comments || []).length;
		};
		let me = this;
		this.timeline_wrapper.remove(this.timeline_actions_wrapper);
		this.timeline_wrapper.prepend(`
				<div class="timeline-item activity-title">
				<h4>${__("Activity")}</h4>
				</div>
			`);
		if (has_communications()) {
			this.timeline_wrapper
				.find(".timeline-item.activity-title")
				.append(
					`
					<div class="d-flex align-items-center show-all-activity">
						<span style="color: var(--text-light); margin:0px 6px;">${__("Show all activity")}</span>
						<label class="switch">
							<input type="checkbox">
							<span class="slider round"></span>
						</label>
					</div>
				`
				)
				.find("input[type=checkbox]")
				.prop("checked", !me.only_communication)
				.on("click", function (e) {
					me.only_communication = !this.checked;
					me.render_timeline_items();
					$(this).tab("show");
				});
		}
		this.timeline_wrapper
			.find(".timeline-item.activity-title")
			.append(this.timeline_actions_wrapper);
	}

	setup_document_email_link() {
		let doc_info = this.doc_info || this.frm.get_docinfo();

		this.document_email_link_wrapper && this.document_email_link_wrapper.remove();

		if (doc_info.document_email) {
			const link = `<a class="document-email-link">${doc_info.document_email}</a>`;
			const message = __("Add to this activity by mailing to {0}", [link.bold()]);

			this.document_email_link_wrapper = $(`
				<div class="timeline-item">
					<div class="timeline-dot"></div>
					<div class="timeline-content">
						<span>${message}</span>
					</div>
				</div>
			`);
			this.timeline_items_wrapper.before(this.document_email_link_wrapper);

			this.document_email_link_wrapper.find(".document-email-link").on("click", (e) => {
				let text = $(e.target).text();
				frappe.utils.copy_to_clipboard(text);
			});
		}
	}

	render_timeline_items() {
		super.render_timeline_items();
		this.add_web_page_view_count();
		frappe.utils.bind_actions_with_object(this.timeline_items_wrapper, this);
	}

	add_web_page_view_count() {
		if (this.frm.doc.route && cint(frappe.boot.website_tracking_enabled)) {
			frappe.utils.get_page_view_count(this.frm.doc.route).then((res) => {
				this.add_timeline_item({
					content: __("{0} Web page views", [res.message]),
					hide_timestamp: true,
				});
			});
		}
	}

	get_creation_message() {
		return {
			creation: this.frm.doc.creation,
			content: get_user_message(
				this.frm.doc.owner,
				__("You created this"),
				__("{0} created this", [get_user_link(this.frm.doc.owner)])
			),
		};
	}

	get_modified_message() {
		return {
			creation: this.frm.doc.modified,
			content: get_user_message(
				this.frm.doc.modified_by,
				__("You last edited this"),
				__("{0} last edited this", [get_user_link(this.frm.doc.modified_by)])
			),
		};
	}

	prepare_timeline_contents() {
		this.timeline_items.push(this.get_creation_message());
		this.timeline_items.push(this.get_modified_message());
		this.timeline_items.push(...this.get_communication_timeline_contents());
		this.timeline_items.push(...this.get_comment_timeline_contents());
		if (!this.only_communication) {
			this.timeline_items.push(...this.get_view_timeline_contents());
			this.timeline_items.push(...this.get_version_timeline_contents());
			this.timeline_items.push(...this.get_share_timeline_contents());
			this.timeline_items.push(...this.get_workflow_timeline_contents());
			this.timeline_items.push(...this.get_like_timeline_contents());
			this.timeline_items.push(...this.get_custom_timeline_contents());
			this.timeline_items.push(...this.get_assignment_timeline_contents());
			this.timeline_items.push(...this.get_attachment_timeline_contents());
			this.timeline_items.push(...this.get_info_timeline_contents());
			this.timeline_items.push(...this.get_milestone_timeline_contents());
		}
	}

	get_view_timeline_contents() {
		let view_timeline_contents = [];
		(this.doc_info.views || []).forEach((view) => {
			view_timeline_contents.push({
				creation: view.creation,
				content: get_user_message(
					view.owner,
					__("You viewed this"),
					__("{0} viewed this", [get_user_link(view.owner)])
				),
			});
		});

		return view_timeline_contents;
	}

	get_communication_timeline_contents(more_communications, more_automated_messages) {
		let email_communications =
			this.get_email_communication_timeline_contents(more_communications);
		let automated_messages = this.get_auto_messages_timeline_contents(more_automated_messages);
		let all_communications = email_communications.concat(automated_messages);

		if (all_communications.length > 20) {
			all_communications.pop();

			if (more_communications || more_automated_messages) {
				all_communications.forEach((message) => {
					if (message.communication_type == "Automated Message") {
						this.doc_info.automated_messages.push(message);
					} else {
						this.doc_info.communications.push(message);
					}
				});
			}

			let last_communication_time =
				all_communications[all_communications.length - 1].creation;
			let load_more_button = {
				creation: last_communication_time,
				content: __("Load More Communications", null, "Form timeline"),
				name: "load-more",
			};
			all_communications.push(load_more_button);
		}

		return all_communications;
	}

	get_email_communication_timeline_contents(more_items) {
		let communication_timeline_contents = [];
		let icon_set = {
			Email: "mail",
			Phone: "call",
			Meeting: "calendar",
			Other: "dot-horizontal",
		};
		let items = more_items ? more_items : this.doc_info.communications || [];
		items.forEach((communication) => {
			let medium = communication.communication_medium;
			communication_timeline_contents.push({
				icon: icon_set[medium],
				icon_size: "sm",
				creation: communication.communication_date,
				is_card: true,
				content: this.get_communication_timeline_content(communication),
				doctype: "Communication",
				id: `communication-${communication.name}`,
				name: communication.name,
			});
		});

		return communication_timeline_contents;
	}

	async get_more_communication_timeline_contents() {
		let more_items = [];
		let start =
			this.doc_info.communications.length + this.doc_info.automated_messages.length - 1;
		let response = await frappe.call({
			method: "frappe.desk.form.load.get_communications",
			args: {
				doctype: this.doc_info.doctype,
				name: this.doc_info.name,
				start: start,
				limit: 21,
			},
		});
		if (response.message) {
			let email_communications = [];
			let automated_messages = [];
			response.message.forEach((message) => {
				if (message.communication_type == "Automated Message") {
					automated_messages.push(message);
				} else {
					email_communications.push(message);
				}
			});
			more_items = this.get_communication_timeline_contents(
				email_communications,
				automated_messages
			);
		}
		return more_items;
	}

	get_communication_timeline_content(doc, allow_reply = true) {
		doc._url = frappe.utils.get_form_link("Communication", doc.name);
		this.set_communication_doc_status(doc);
		if (doc.attachments && typeof doc.attachments === "string") {
			doc.attachments = JSON.parse(doc.attachments);
		}
		doc.owner = doc.sender;
		doc.user_full_name = doc.sender_full_name;
		doc.content = frappe.dom.remove_script_and_style(doc.content);
		let communication_content = $(frappe.render_template("timeline_message_box", { doc }));
		if (allow_reply) {
			this.setup_reply(communication_content, doc);
		}
		return communication_content;
	}

	set_communication_doc_status(doc) {
		let indicator_color = "red";
		if (["Sent", "Clicked"].includes(doc.delivery_status)) {
			indicator_color = "green";
		} else if (["Sending", "Scheduled"].includes(doc.delivery_status)) {
			indicator_color = "orange";
		} else if (["Opened", "Read"].includes(doc.delivery_status)) {
			indicator_color = "blue";
		} else if (doc.delivery_status == "Error") {
			indicator_color = "red";
		}
		doc._doc_status = doc.delivery_status;
		doc._doc_status_indicator = indicator_color;
	}

	get_auto_messages_timeline_contents(more_items) {
		let auto_messages_timeline_contents = [];
		let items = more_items ? more_items : this.doc_info.automated_messages || [];
		items.forEach((message) => {
			auto_messages_timeline_contents.push({
				icon: "notification",
				icon_size: "sm",
				creation: message.creation,
				is_card: true,
				content: this.get_communication_timeline_content(message, false),
				doctype: "Communication",
				name: message.name,
			});
		});
		return auto_messages_timeline_contents;
	}

	get_comment_timeline_contents() {
		let comment_timeline_contents = [];
		(this.doc_info.comments || []).forEach((comment) => {
			comment_timeline_contents.push(this.get_comment_timeline_item(comment));
		});
		return comment_timeline_contents;
	}

	get_comment_timeline_item(comment) {
		return {
			icon: "es-line-chat-alt",
			icon_size: "sm",
			creation: comment.creation,
			is_card: true,
			doctype: "Comment",
			id: `comment-${comment.name}`,
			name: comment.name,
			content: this.get_comment_timeline_content(comment),
		};
	}

	get_comment_timeline_content(doc) {
		doc.content = frappe.dom.remove_script_and_style(doc.content);
		const comment_content = $(frappe.render_template("timeline_message_box", { doc }));
		this.setup_comment_actions(comment_content, doc);
		return comment_content;
	}

	get_version_timeline_contents() {
		let version_timeline_contents = [];
		(this.doc_info.versions || []).forEach((version) => {
			const contents = get_version_timeline_content(version, this.frm);
			contents.forEach((content) => {
				version_timeline_contents.push({
					creation: version.creation,
					content: content,
				});
			});
		});
		return version_timeline_contents;
	}

	get_share_timeline_contents() {
		let share_timeline_contents = [];
		(this.doc_info.share_logs || []).forEach((share_log) => {
			share_timeline_contents.push({
				creation: share_log.creation,
				content: share_log.content,
			});
		});
		return share_timeline_contents;
	}

	get_assignment_timeline_contents() {
		let assignment_timeline_contents = [];
		(this.doc_info.assignment_logs || []).forEach((assignment_log) => {
			assignment_timeline_contents.push({
				creation: assignment_log.creation,
				content: assignment_log.content,
			});
		});
		return assignment_timeline_contents;
	}

	get_info_timeline_contents() {
		let info_timeline_contents = [];
		(this.doc_info.info_logs || []).forEach((info_log) => {
			info_timeline_contents.push({
				creation: info_log.creation,
				content: `${get_user_link(info_log.owner)} ${info_log.content}`,
			});
		});
		return info_timeline_contents;
	}

	get_attachment_timeline_contents() {
		let attachment_timeline_contents = [];

		(this.doc_info.attachment_logs || []).forEach((attachment_log) => {
			const is_file_upload = attachment_log.comment_type == "Attachment";
			const user_link = get_user_link(attachment_log.owner);
			const filename = attachment_log.content;
			const timeline_content = is_file_upload
				? get_user_message(
						attachment_log.owner,
						__("You attached {0}", [filename], "Form timeline"),
						__("{0} attached {1}", [user_link, filename], "Form timeline")
				  )
				: get_user_message(
						attachment_log.owner,
						__("You removed attachment {0}", [filename], "Form timeline"),
						__("{0} removed attachment {1}", [user_link, filename], "Form timeline")
				  );

			attachment_timeline_contents.push({
				icon: is_file_upload ? "es-line-attachment" : "es-line-delete",
				icon_size: "sm",
				creation: attachment_log.creation,
				content: timeline_content,
			});
		});

		return attachment_timeline_contents;
	}

	get_milestone_timeline_contents() {
		let milestone_timeline_contents = [];

		(this.doc_info.milestones || []).forEach((milestone_log) => {
			const field = frappe.meta.get_label(this.frm.doctype, milestone_log.track_field);
			const value = milestone_log.value.bold();
			const user_link = get_user_link(milestone_log.owner);
			const timeline_content = get_user_message(
				milestone_log.owner,
				__("You changed {0} to {1}", [field, value], "Form timeline"),
				__("{0} changed {1} to {2}", [user_link, field, value], "Form timeline")
			);

			milestone_timeline_contents.push({
				icon: "milestone",
				creation: milestone_log.creation,
				content: timeline_content,
			});
		});

		return milestone_timeline_contents;
	}

	get_like_timeline_contents() {
		let like_timeline_contents = [];

		(this.doc_info.like_logs || []).forEach((like_log) => {
			const timeline_content = get_user_message(
				like_log.owner,
				__("You Liked"),
				__("{0} Liked", [get_user_link(like_log.owner)])
			);

			like_timeline_contents.push({
				icon: "es-line-like",
				icon_size: "sm",
				creation: like_log.creation,
				content: timeline_content,
				title: "Like",
			});
		});

		return like_timeline_contents;
	}

	get_workflow_timeline_contents() {
		let workflow_timeline_contents = [];
		(this.doc_info.workflow_logs || []).forEach((workflow_log) => {
			workflow_timeline_contents.push({
				icon: "branch",
				icon_size: "sm",
				creation: workflow_log.creation,
				content: `${get_user_link(workflow_log.owner)} ${__(workflow_log.content)}`,
				title: "Workflow",
			});
		});
		return workflow_timeline_contents;
	}

	get_custom_timeline_contents() {
		let custom_timeline_contents = [];
		(this.doc_info.additional_timeline_content || []).forEach((custom_item) => {
			if (custom_item.timeline_badge) {
				custom_timeline_contents.push({
					timeline_badge: custom_item.timeline_badge,
					creation: custom_item.creation,
					content: frappe.utils.eval(custom_item.method, {
						custom_item: custom_item,
					}),
				});
			} else {
				custom_timeline_contents.push({
					icon: custom_item.icon,
					timeline_badge: custom_item.timeline_badge,
					icon_size: "sm",
					is_card: custom_item.is_card,
					creation: custom_item.creation,
					content:
						custom_item.content ||
						frappe.render_template(custom_item.template, custom_item.template_data),
				});
			}
		});
		return custom_timeline_contents;
	}

	setup_reply(communication_box, communication_doc) {
		let actions = communication_box.find(".custom-actions");
		let reply = $(`<a class="action-btn reply">${frappe.utils.icon("reply", "md")}</a>`).click(
			() => {
				this.compose_mail(communication_doc);
			}
		);
		let reply_all = $(
			`<a class="action-btn reply-all">${frappe.utils.icon("reply-all", "md")}</a>`
		).click(() => {
			this.compose_mail(communication_doc, true);
		});
		if (frappe.is_mobile()) {
			this.add_dropdown_item(communication_box, [reply, reply_all]);
		} else {
			actions.append(reply);
			actions.append(reply_all);
		}
	}
	add_dropdown_item(timeline_box, menu_items) {
		let more_actions = timeline_box.find(".more-actions > .dropdown-menu > li");
		menu_items.forEach((m) => {
			let action_name = m[0].classList[1];
			let formatted_action_name =
				String(action_name).charAt(0).toUpperCase() + String(action_name).slice(1);
			m.empty();
			m.append(
				__("{0}", [frappe.utils.to_title_case(formatted_action_name.replace("-", " "))])
			);
			m.removeClass();
			m.addClass("dropdown-item");
			more_actions.append(m);
		});
	}
	compose_mail(communication_doc = null, reply_all = false) {
		const args = {
			doc: this.frm.doc,
			frm: this.frm,
			recipients:
				communication_doc && communication_doc.sender != frappe.session.user_email
					? communication_doc.sender
					: this.get_recipient(),
			is_a_reply: Boolean(communication_doc),
			title: communication_doc ? __("Reply") : null,
			last_email: communication_doc,
			subject: communication_doc && communication_doc.subject,
			reply_all: reply_all,
		};

		const email_accounts = frappe.boot.email_accounts
			.filter((account) => {
				return (
					!["All Accounts", "Sent", "Spam", "Trash"].includes(account.email_account) &&
					account.enable_outgoing
				);
			})
			.map((e) => e.email_id);

		if (communication_doc && args.is_a_reply) {
			args.cc = "";
			if (
				email_accounts.includes(frappe.session.user_email) &&
				communication_doc.sender != frappe.session.user_email
			) {
				// add recipients to cc if replying sender is different from last email
				const recipients = communication_doc.recipients.split(",").map((r) => r.trim());
				args.cc =
					recipients.filter((r) => r != frappe.session.user_email).join(", ") + ", ";
			}
			if (reply_all) {
				// if reply_all then add cc and bcc as well.
				args.cc += cstr(communication_doc.cc);
				args.bcc = cstr(communication_doc.bcc);
			}
		}

		if (this.frm.doctype === "Communication") {
			args.message = "";
			args.last_email = this.frm.doc;
			args.recipients = this.frm.doc.sender;
			args.subject = __("Re: {0}", [this.frm.doc.subject]);
		} else {
			const comment_value = frappe.markdown(this.frm.comment_box.get_value());
			args.message = strip_html(comment_value) ? comment_value : "";
		}

		new frappe.views.CommunicationComposer(args);
	}

	get_recipient() {
		if (this.frm.email_field) {
			return this.frm.doc[this.frm.email_field];
		} else {
			return this.frm.doc.email_id || this.frm.doc.email || "";
		}
	}

	setup_comment_actions(comment_wrapper, doc) {
		let edit_wrapper = $(`<div class="comment-edit-box">`).hide();
		let edit_box = this.make_editable(edit_wrapper);
		let content_wrapper = comment_wrapper.find(".content");
		let more_actions_wrapper = comment_wrapper.find(".more-actions");
		const dropdown_menu = more_actions_wrapper.find(".dropdown-menu li");

		if (frappe.session.user == doc.owner || frappe.user.has_role("System Manager")) {
			if (frappe.model.can_delete("Comment")) {
				const delete_option = $(`
					<a class="dropdown-item">${__("Delete")}</a>
				`).click(() => this.delete_comment(doc.name));
				dropdown_menu.append(delete_option);
			}

			const un_publish_button = $(`
				<a class="dropdown-item">${doc.published ? __("Unpublish") : __("Publish")}</a>
			`).click(() => this.update_comment_publicity(doc.name, !doc.published));
			dropdown_menu.append(un_publish_button);
		}

		let dismiss_button = $(`
			<button class="btn btn-link action-btn">
				${__("Dismiss")}
			</button>
		`).click(() => edit_button.toggle_edit_mode());
		dismiss_button.hide();

		edit_box.set_value(doc.content);

		edit_box.on_submit = (value) => {
			content_wrapper.empty();
			content_wrapper.append(value);
			edit_button.prop("disabled", true);
			edit_box.quill.enable(false);

			doc.content = value;
			this.update_comment(doc.name, value)
				.then(edit_button.toggle_edit_mode)
				.finally(() => {
					edit_button.prop("disabled", false);
					edit_box.quill.enable(true);
				});
		};

		content_wrapper.after(edit_wrapper);

		let edit_button = $();
		let current_user = frappe.session.user;
		let can_edit = ["Administrator", doc.owner].includes(current_user);
		if (can_edit) {
			edit_button = $(
				`<button class="btn edit btn-link action-btn">${__("Edit")}</a>`
			).click(() => {
				edit_button.edit_mode ? edit_box.submit() : edit_button.toggle_edit_mode();
			});
		}

		edit_button.toggle_edit_mode = () => {
			edit_button.edit_mode = !edit_button.edit_mode;
			edit_button.text(edit_button.edit_mode ? __("Save") : __("Edit"));
			more_actions_wrapper.toggle(!edit_button.edit_mode);
			dismiss_button.toggle(edit_button.edit_mode);
			edit_wrapper.toggle(edit_button.edit_mode);
			content_wrapper.toggle(!edit_button.edit_mode);
		};
		let actions_wrapper = comment_wrapper.find(".custom-actions");
		if (frappe.is_mobile()) {
			if (can_edit) {
				this.add_dropdown_item(comment_wrapper, [edit_button]);
			}
		} else {
			actions_wrapper.append(edit_button);
			actions_wrapper.append(dismiss_button);
		}
	}

	make_editable(container) {
		return frappe.ui.form.make_control({
			parent: container,
			df: {
				fieldtype: "Comment",
				fieldname: "comment",
				label: "Comment",
			},
			enable_mentions: true,
			render_input: true,
			only_input: true,
			no_wrapper: true,
		});
	}

	update_comment(name, content) {
		return frappe
			.xcall("frappe.desk.form.utils.update_comment", { name, content })
			.then(() => {
				frappe.utils.play_sound("click");
			});
	}

	get_last_email(from_recipient) {
		/**
		 * Return the latest email communication.
		 *
		 * @param {boolean} from_recipient If true, only considers emails where current form's recipient is the sender.
		 * @returns {object|null} The latest email communication, or null if no communication is found.
		 */

		const communications = this.frm.get_docinfo().communications || [];
		const recipient = this.get_recipient();

		const filtered_records = communications
			.filter(
				(record) =>
					record.communication_type === "Communication" &&
					record.communication_medium === "Email" &&
					(!from_recipient || record.sender === recipient)
			)
			.sort((a, b) => b.creation - a.creation);

		return filtered_records[0] || null;
	}

	delete_comment(comment_name) {
		frappe.confirm(__("Delete comment?"), () => {
			return frappe
				.xcall("frappe.client.delete", {
					doctype: "Comment",
					name: comment_name,
				})
				.then(() => {
					frappe.utils.play_sound("delete");
				});
		});
	}

	update_comment_publicity(comment_name, publish) {
		let message;
		if (publish) {
			message = __(
				"Would you like to publish this comment? This means it will become visible to website/portal users."
			);
		} else {
			message = __(
				"Would you like to unpublish this comment? This means it will no longer be visible to website/portal users."
			);
		}

		frappe.confirm(message, () => {
			return frappe
				.xcall("frappe.desk.form.utils.update_comment_publicity", {
					name: comment_name,
					publish,
				})
				.then(() => {
					frappe.utils.play_sound("click");
				});
		});
	}

	copy_link(ev) {
		let doc_link = frappe.urllib.get_full_url(
			frappe.utils.get_form_link(this.frm.doctype, this.frm.docname)
		);
		let element_id = $(ev.currentTarget).closest(".timeline-content").attr("id");
		frappe.utils.copy_to_clipboard(`${doc_link}#${element_id}`);
	}
}

export default FormTimeline;
