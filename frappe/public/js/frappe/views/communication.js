// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

import localforage from "localforage";

frappe.last_edited_communication = {};
const separator_element = "<div>---</div>";
// Quill uses <p>---</p>; match both when stripping quoted content
const separator_regex = /<(?:div|p)(?:\s[^>]*)?>---<\/(?:div|p)>/i;

frappe.views.CommunicationComposer = class {
	constructor(opts) {
		$.extend(this, opts);
		if (!this.doc) {
			this.doc = (this.frm && this.frm.doc) || {};
		}

		this.make();
	}

	make() {
		const me = this;

		this.dialog = new frappe.ui.Dialog({
			title: this.title || this.subject || __("New Email"),
			no_submit_on_enter: true,
			fields: this.get_fields(),
			primary_action_label: __("Send", null, "Send Email"),
			primary_action() {
				me.send_action();
			},
			secondary_action_label: __("Discard", null, "Discard Email"),
			secondary_action() {
				me.dialog.hide();
				me.clear_cache();
			},
			size: "large",
			minimizable: true,
			// The composer is docked, not a modal over the page: navigating away
			// must leave it exactly as the user left it. Without this, changing
			// route auto-minimises it (container.js change_to), which also
			// inverted the minimise button — it restored instead of minimising.
			keep_open: true,
		});

		$(this.dialog.$wrapper.find(".form-section").get(0)).addClass("to_section");
		this.setup_composer_shell();
		this.prepare();
		this.render_composer_layout();
		this.dialog.show();

		if (this.frm) {
			$(document).trigger("form-typing", [this.frm]);
		}
	}

	setup_composer_shell() {
		// Docked floating shell (styled in email_composer.scss); no backdrop so the form stays usable.
		const $wrapper = this.dialog.$wrapper;
		$wrapper.addClass("email-composer-modal");
		$wrapper.attr("data-backdrop", "false");

		// Repurpose the dialog's existing minimise button into a full-screen toggle.
		$wrapper
			.find(".btn-modal-minimize")
			.removeClass("btn-modal-minimize")
			.attr("title", __("Full screen"))
			.off("click")
			.on("click", () => $wrapper.toggleClass("expanded"));

		// Add the minimise button on the left, reusing the dialog's minimize logic.
		// It skips .btn-modal-minimize so toggle_minimize() doesn't swap in a missing "collapse" icon.
		const $minimize = $(
			frappe.ui.button.html({
				icon: "minus",
				variant: "ghost",
				title: __("Minimize"),
				css_class: "btn-modal-collapse icon-btn",
			})
		).on("click", () => this.dialog.toggle_minimize());
		$wrapper.find(".modal-header .modal-actions").prepend($minimize);
	}

	render_composer_layout() {
		// Move the live field controls out of Frappe's default form layout into our own
		// skeleton (nodes are MOVED, not cloned, so every control keeps its state and logic).
		const $body = this.dialog.$body;
		const $original = $body.children();

		this.$composer = $(`
			<div class="email-composer">
				<div class="email-composer-recipients">
					<div class="email-composer-row email-composer-sender-row hidden" data-slot="sender"></div>
					<div class="email-composer-row email-composer-to-row">
						<div class="email-composer-to-input" data-slot="recipients"></div>
						<div class="email-composer-recipient-toggles">
							${frappe.ui.button.html({
								label: __("CC"),
								variant: "ghost",
								css_class: "email-composer-toggle",
								attrs: { "data-target": "cc" },
							})}
							${frappe.ui.button.html({
								label: __("BCC"),
								variant: "ghost",
								css_class: "email-composer-toggle",
								attrs: { "data-target": "bcc" },
							})}
						</div>
					</div>
					<div class="email-composer-row email-composer-cc-row hidden" data-slot="cc"></div>
					<div class="email-composer-row email-composer-bcc-row hidden" data-slot="bcc"></div>
					<div class="email-composer-row email-composer-subject-row">
						<div class="email-composer-subject" data-slot="subject"></div>
						<div class="email-composer-template dropdown">
							${frappe.ui.button.html({
								label: __("Add template"),
								variant: "ghost",
								icon_right: "chevron-down",
								css_class: "email-composer-add-template",
								attrs: { "data-toggle": "dropdown", "data-display": "static" },
							})}
							<div class="dropdown-menu dropdown-menu-right"></div>
							<div data-slot="email_template"></div>
						</div>
					</div>
					${frappe.ui.divider.html()}
				</div>
				<div class="email-composer-html-toggles hidden">
					<div data-slot="use_html"></div>
					<div data-slot="add_css"></div>
				</div>
				<div class="email-composer-message-area">
					<div data-slot="content"></div>
					<div data-slot="html_content"></div>
				</div>
				<div class="email-composer-attachments" data-slot="select_attachments"></div>
				<div class="email-composer-print-format"></div>
				<div class="email-composer-footer">
					<div class="email-composer-toolbar-slot hidden"></div>
					<div class="email-composer-banner hidden">
						<span class="email-composer-banner__text"></span>
						<button class="btn btn-ghost email-composer-banner__close" data-action="dismiss-banner">${frappe.utils.icon(
							"x",
							"xs"
						)}</button>
					</div>
					<div class="email-composer-action-bar">
						<div class="email-composer-icon-row">
							<div class="dropdown">
								<button class="btn btn-ghost icon-btn" data-action="attach" data-toggle="dropdown" title="${__(
									"Attach files"
								)}">${frappe.utils.icon("paperclip", "sm")}</button>
								<div class="dropdown-menu email-composer-attach-menu">
									<a class="dropdown-item" data-action="select-attachments" href="#">
										${frappe.utils.icon("paperclip", "sm")}&nbsp;${__("Select attachments")}
									</a>
									<a class="dropdown-item" data-action="add-attachments" href="#">
										${frappe.utils.icon("plus", "sm")}&nbsp;${__("Add new attachments")}
									</a>
								</div>
							</div>
							<div class="dropdown">
								<button class="btn btn-ghost icon-btn" data-action="print" data-toggle="dropdown" title="${__(
									"Attach document print"
								)}">${frappe.utils.icon("printer", "sm")}</button>
								<div class="dropdown-menu dropdown-menu-right email-composer-print-menu"></div>
							</div>
							<button class="btn btn-ghost icon-btn" data-action="format" title="${__(
								"Formatting options"
							)}">${frappe.utils.icon("type", "sm")}</button>
							<div class="dropdown">
								<button class="btn btn-ghost icon-btn" data-toggle="dropdown" title="${__(
									"More options"
								)}">${frappe.utils.icon("ellipsis", "sm")}</button>
								<div class="dropdown-menu dropdown-menu-right email-composer-more-menu">
									<div class="dropdown-item email-composer-menu-toggle switch-control" data-action="send-read-receipt">
										${frappe.utils.icon("mail-open", "sm")}
										<span>${__("Send read receipt")}</span>
										<span class="switch-visual"><span class="switch-thumb"></span></span>
									</div>
									<div class="dropdown-item email-composer-menu-toggle switch-control" data-action="send-me-a-copy">
										${frappe.utils.icon("copy", "sm")}
										<span>${__("Send me a copy")}</span>
										<span class="switch-visual"><span class="switch-thumb"></span></span>
									</div>
								</div>
							</div>
						</div>
						<div class="email-composer-action-bar__right">
							<button class="btn btn-ghost btn-sm" data-action="discard">${__("Discard")}</button>
							<div class="email-composer-send-group dropdown" data-slot="send-button">
								${frappe.ui.button.html({
									label: __("Send"),
									variant: "solid",
									size: "sm",
									css_class: "email-composer-send-btn",
									attrs: { "data-action": "send-now" },
								})}
								${frappe.ui.button.html({
									icon: "chevron-down",
									variant: "solid",
									size: "sm",
									css_class: "email-composer-send-toggle",
									title: __("More send options"),
									attrs: { "data-toggle": "dropdown" },
								})}
								<div class="dropdown-menu dropdown-menu-right email-composer-send-menu">
									<a class="dropdown-item" data-action="schedule" href="#">
										${frappe.utils.icon("calendar", "sm")}&nbsp;${__("Schedule email")}
									</a>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		`);
		$body.prepend(this.$composer);

		[
			"sender",
			"recipients",
			"cc",
			"bcc",
			"email_template",
			"use_html",
			"add_css",
			"subject",
			"content",
			"html_content",
			"select_attachments",
		].forEach((fieldname) => {
			const $control = $body.find(`.frappe-control[data-fieldname="${fieldname}"]`);
			if ($control.length) {
				this.$composer.find(`[data-slot="${fieldname}"]`).append($control);
			}
		});

		// Subject renders as an inline placeholder heading, not a labelled field.
		this.dialog.fields_dict.subject.$input?.attr("placeholder", __("Subject"));

		// Show the sender row only when the user has more than one outgoing account.
		if (this.user_email_accounts?.length > 1) {
			this.$composer.find(".email-composer-sender-row").removeClass("hidden");
		}

		// Cc / Bcc ghost buttons toggle their respective rows; the button mutes to
		// grey (.active) while its row is open.
		this.$composer.find(".email-composer-toggle").on("click", (e) => {
			const $btn = $(e.currentTarget);
			const target = $btn.data("target");
			const $row = this.$composer.find(`.email-composer-${target}-row`);
			$row.toggleClass("hidden");
			$btn.toggleClass("active", !$row.hasClass("hidden"));
		});

		this.setup_template_dropdown();

		// Keep the dialog's real send button hidden in the send group — the visible
		// "Send ▾" toggle opens the menu, and "Send now" triggers this to send.
		const $sendBtn = this.dialog.$wrapper.find(".btn-modal-primary");
		if ($sendBtn.length) {
			this.$composer.find('[data-slot="send-button"]').prepend($sendBtn.addClass("hidden"));
		}

		this.$composer.find('[data-action="discard"]').on("click", () => {
			this.dialog.hide();
			this.clear_cache();
		});
		// "Add new attachments" uploads a file (the old paperclip behaviour);
		// "Select attachments" picks from what's already on the document.
		this.$composer.find('[data-action="add-attachments"]').on("click", (e) => {
			e.preventDefault();
			$body.find(".add-more-attachments button").trigger("click");
		});
		this.$composer.find('[data-action="select-attachments"]').on("click", (e) => {
			e.preventDefault();
			this.open_attachment_picker();
		});

		this.$composer.find('[data-action="format"]').on("click", (e) => {
			$(e.currentTarget).toggleClass("active");
			this.setup_toolbar();
			this.$composer.find(".email-composer-toolbar-slot").toggleClass("hidden");
		});

		const fields = this.dialog.fields_dict;

		const $banner = this.$composer.find(".email-composer-banner");
		this.$composer.find('[data-action="dismiss-banner"]').on("click", () => {
			$banner.addClass("hidden");
		});
		const updateBanner = () => {
			const copy = !!fields.send_me_a_copy.get_value();
			const receipt = !!fields.send_read_receipt.get_value();
			let text = "";
			if (copy && receipt) {
				text = __("You will receive a copy of this email and a read receipt");
			} else if (copy) {
				text = __("You will receive a copy of this email");
			} else if (receipt) {
				text = __("You will receive a read receipt");
			}
			$banner.find(".email-composer-banner__text").text(text);
			$banner.toggleClass("hidden", !text);
		};

		const bindCheckIcon = (action, fieldname) => {
			const $item = this.$composer.find(`[data-action="${action}"]`);
			const field = fields[fieldname];
			let active = !!(field.get_value() || field.df.default);
			field.set_input(active ? 1 : 0);
			$item.toggleClass("active", active);

			$item.on("click", (e) => {
				// Keep the dropdown open so users can toggle multiple options in one click.
				if ($item.hasClass("email-composer-menu-toggle")) e.stopPropagation();
				active = !active;
				field.set_input(active ? 1 : 0);
				$item.toggleClass("active", active);
				updateBanner();
			});
		};

		let syncPrintMenu = () => {};

		// The attached document print renders as its own card under the attachment
		// chips: title + "format • letter head • language", with edit (opens the
		// settings dialog) and delete. The hidden `attach_document_print` Check
		// stays the single source of truth that send_action reads — this card and
		// the printer dropdown are only views onto it.
		const renderPrintRow = (active) => {
			const $slot = this.$composer.find(".email-composer-print-format").empty();
			if (!active) return;

			const $card = $(`
				<div class="email-composer-print-card">
					<div class="email-composer-print-card__content">
						<div class="email-composer-print-card__title" role="button" tabindex="0" title="${__(
							"Preview"
						)}">${__("Print format")}</div>
						<div class="email-composer-print-card__meta"></div>
					</div>
					<div class="email-composer-print-card__actions">
						<button type="button" class="btn btn-ghost icon-btn" data-action="edit-print" title="${__(
							"Change print settings"
						)}">${frappe.utils.icon("pencil", "sm")}</button>
						<button type="button" class="btn btn-ghost icon-btn" data-action="remove-print" title="${__(
							"Remove"
						)}">${frappe.utils.icon("trash", "sm")}</button>
					</div>
				</div>
			`);

			// Only the "Print format" title opens the preview — the meta line and the
			// rest of the card stay inert, so there's no ambiguity about what the
			// click target is.
			const $title = $card.find(".email-composer-print-card__title");
			$title.on("click", () => this.open_print_preview());
			$title.on("keydown", (e) => {
				if (e.key !== "Enter" && e.key !== " ") return;
				e.preventDefault();
				this.open_print_preview();
			});

			$card.find('[data-action="edit-print"]').on("click", (e) => {
				e.preventDefault();
				this.open_print_settings();
			});
			$card.find('[data-action="remove-print"]').on("click", (e) => {
				e.preventDefault();
				fields.attach_document_print.set_input(0);
				renderPrintRow(false);
				syncPrintMenu();
			});

			$slot.append($card);
			this.render_print_card_meta();
		};

		// Reachable from open_print_settings(), which lives outside this closure.
		this.render_print_card = renderPrintRow;

		bindCheckIcon("send-me-a-copy", "send_me_a_copy");
		bindCheckIcon("send-read-receipt", "send_read_receipt");

		const $printBtn = this.$composer.find('[data-action="print"]');
		const $printMenu = this.$composer.find(".email-composer-print-menu");
		if (!this.frm) {
			$printBtn.parent().hide();
		} else {
			const formats = frappe.meta.get_print_formats(this.frm.meta.name) || [];
			syncPrintMenu = () => {
				const current = fields.select_print_format.get_value();
				$printBtn.toggleClass("active", !!fields.attach_document_print.get_value());
				$printMenu.find(".dropdown-item").each(function () {
					$(this).toggleClass("selected", $(this).data("format") === current);
				});
			};
			formats.forEach((f) => {
				const $item = $(
					`<a class="dropdown-item" href="#" data-format="${frappe.utils.escape_html(
						f
					)}">${frappe.utils.escape_html(f)}</a>`
				);
				$item.on("click", async (e) => {
					e.preventDefault();
					// await: set_value is async, so repainting straight after it would
					// read the previous format and leave the card's meta line stale
					await fields.select_print_format.set_value(f);
					if (!fields.attach_document_print.get_value()) {
						fields.attach_document_print.set_input(1);
					}
					// re-render unconditionally: picking a different format while the
					// print is already attached must refresh the card's meta line too
					renderPrintRow(true);
					syncPrintMenu();
				});
				$printMenu.append($item);
			});
			syncPrintMenu();
		}
		// Reachable from open_print_settings(), which lives outside this closure.
		this.sync_print_menu = () => syncPrintMenu();
		updateBanner();

		this.$composer.find('[data-action="send-now"]').on("click", (e) => {
			e.preventDefault();
			this.$composer.find(".btn-modal-primary").trigger("click");
		});

		this.$composer.find('[data-action="schedule"]').on("click", (e) => {
			e.preventDefault();
			frappe.prompt(
				{
					label: __("Schedule Send At"),
					fieldname: "schedule_at",
					fieldtype: "Datetime",
					default: fields.send_after.get_value(),
				},
				(values) => {
					this.dialog.set_value("send_after", values.schedule_at);
				},
				__("Schedule Send")
			);
		});

		$original.hide();
	}

	setup_toolbar() {
		const $slot = this.$composer.find(".email-composer-toolbar-slot");
		if ($slot.children(".ql-toolbar").length) return; // already relocated + wired

		const $toolbar = this.$composer.find(
			'.frappe-control[data-fieldname="content"] .ql-toolbar'
		);
		if (!$toolbar.length) return; // Quill hasn't built the toolbar yet

		// Move Quill's toolbar out of the message body into its slot in the sticky
		// footer, pinned above the Send row (Gmail-style). Its click handlers are
		// bound to the element, so relocating the node keeps them live.
		$slot.append($toolbar);

		// Order the tool groups by everyday priority and collapse the rarely-used
		// ones behind a "⋯" toggle, so the row stays clean without hiding common
		// tools. Each group is located by a marker class on one of its controls
		// (Quill's own ql-* classes) rather than a positional index.
		const group = (marker) => $toolbar.find(marker).first().closest(".ql-formats");
		const visible = [
			".ql-header", // text style
			".ql-size",
			".ql-bold", // bold / italic / underline / strike / clean
			".ql-color", // text + background colour
			".ql-list",
			".ql-align",
			".ql-link", // link + image
		];
		const overflow = [".ql-blockquote", ".ql-direction", ".ql-indent", ".ql-table"];

		visible.forEach((marker) => $toolbar.append(group(marker)));

		const $more = $(
			`<button type="button" class="email-composer-toolbar-more" title="${__(
				"More options"
			)}">${frappe.utils.icon("ellipsis", "sm")}</button>`
		);
		$toolbar.append($more);

		overflow.forEach((marker) =>
			$toolbar.append(group(marker).addClass("email-composer-toolbar-overflow"))
		);

		$more.on("click", () => {
			const expanded = $toolbar.toggleClass("show-overflow").hasClass("show-overflow");
			// Reuse Quill's own active-button styling for the pressed state.
			$more.toggleClass("ql-active", expanded);
		});
	}

	setup_template_dropdown() {
		const $menu = this.$composer.find(".email-composer-template .dropdown-menu");

		frappe.call({
			method: "frappe.email.doctype.email_template.email_template.get_email_templates",
			args: {
				doctype: "Email Template",
				txt: "",
				searchfield: "name",
				start: 0,
				page_len: 0,
				filters: { reference_doctype: this.frm?.doctype || "" },
			},
			callback: (r) => {
				const templates = r.message || [];
				if (!templates.length) {
					$menu.append(
						`<span class="dropdown-item disabled">${__("No templates")}</span>`
					);
					return;
				}
				templates.forEach(([name]) => {
					$(`<a class="dropdown-item" href="#"></a>`)
						.text(name)
						.on("click", (e) => {
							e.preventDefault();
							this.apply_email_template(name);
						})
						.appendTo($menu);
				});
			},
		});
	}

	get_fields() {
		let me = this;
		const fields = [
			{
				label: __("To", null, "Email Recipients"),
				fieldtype: "MultiSelect Pills",
				reqd: 0,
				fieldname: "recipients",
				default: this.get_default_recipients("recipients"),
				ignore_validation: true,
			},
			{
				label: __("CC", null, "Email Recipients"),
				fieldtype: "MultiSelect Pills",
				fieldname: "cc",
				default: this.get_default_recipients("cc"),
				ignore_validation: true,
			},
			{
				label: __("BCC", null, "Email Recipients"),
				fieldtype: "MultiSelect Pills",
				fieldname: "bcc",
				default: this.get_default_recipients("bcc"),
				ignore_validation: true,
			},
			{
				label: __("Schedule Send At"),
				fieldtype: "Datetime",
				fieldname: "send_after",
			},
			{
				fieldtype: "Section Break",
				fieldname: "email_template_section_break",
				hidden: 1,
			},
			{
				label: __("Email Template"),
				fieldtype: "Link",
				options: "Email Template",
				fieldname: "email_template",
				get_query: function () {
					if (me.frm?.doctype) {
						return {
							query: "frappe.email.doctype.email_template.email_template.get_email_templates",
							filters: { reference_doctype: me.frm.doctype },
						};
					}
				},
				onchange: async function () {
					const email_template = this.value;
					if (!email_template) return me.hide_use_html_field();
					await me.check_email_template_html(email_template);
				},
			},
			{
				label: __("Use HTML"),
				fieldtype: "Check",
				fieldname: "use_html",
				default: 0,
				hidden: 1,
				description: "Use Raw HTML email editor.",
				onchange: (event) => {
					me.on_use_html_toggle(event);
				},
			},
			{ fieldtype: "Section Break" },
			{
				label: __("Subject"),
				fieldtype: "Data",
				reqd: 1,
				fieldname: "subject",
				length: 524288,
			},
			{
				label: __("Message"),
				fieldtype: "Text Editor",
				fieldname: "content",
				onchange: frappe.utils.debounce(this.save_as_draft.bind(this), 300),
				depends_on: "eval:!doc.use_html",
			},
			{
				label: __("HTML Message"),
				fieldtype: "Code",
				fieldname: "html_content",
				onchange: frappe.utils.debounce(this.save_as_draft.bind(this), 300),
				depends_on: "eval:doc.use_html",
				options: "HTML",
			},
			{
				fieldtype: "Button",
				label: __("Add Signature"),
				fieldname: "add_signature",
				hidden: 1,
				click: async () => {
					let sender_email = this.dialog.get_value("sender") || "";
					this.content_set = false;
					await this.set_content(sender_email);
				},
			},
			{ fieldtype: "Section Break" },
			{
				label: __("Send me a copy"),
				fieldtype: "Check",
				fieldname: "send_me_a_copy",
				default: frappe.boot.user.send_me_a_copy,
			},
			{
				label: __("Send Read Receipt"),
				fieldtype: "Check",
				fieldname: "send_read_receipt",
				default: frappe.boot.user.send_read_receipt,
			},
			{
				label: __("Attach Document Print"),
				fieldtype: "Check",
				fieldname: "attach_document_print",
			},
			{
				label: __("Select Print Format"),
				fieldtype: "Select",
				fieldname: "select_print_format",
				onchange: function () {
					me.guess_language();
				},
			},
			{
				label: __("Letter Head"),
				fieldtype: "Link",
				options: "Letter Head",
				fieldname: "select_letter_head",
			},
			{
				label: __("Print Language"),
				fieldtype: "Link",
				options: "Language",
				fieldname: "print_language",
				default: frappe.boot.lang,
				depends_on: "attach_document_print",
			},
			{ fieldtype: "Column Break" },
			{
				label: __("Add CSS"),
				fieldtype: "Check",
				fieldname: "add_css",
				default: 1,
				depends_on: "eval:doc.use_html",
			},
			{
				label: __("Select Attachments"),
				fieldtype: "HTML",
				fieldname: "select_attachments",
			},
		];

		// add from if user has access to multiple email accounts
		const email_accounts = frappe.boot.email_accounts.filter((account) => {
			return (
				!["All Accounts", "Sent", "Spam", "Trash"].includes(account.email_account) &&
				account.enable_outgoing
			);
		});

		if (email_accounts.length) {
			this.user_email_accounts = email_accounts.map(function (e) {
				return e.email_id;
			});

			fields.unshift({
				label: __("From", null, "Email Sender"),
				fieldtype: "Autocomplete",
				reqd: 1,
				fieldname: "sender",
				options: this.user_email_accounts,
				onchange: () => {
					this.setup_recipients_if_reply();
				},
			});
			//Preselect email senders if there is only one
			if (this.user_email_accounts.length == 1) {
				this["sender"] = this.user_email_accounts;
			} else if (this.user_email_accounts.includes(frappe.session.user_email)) {
				this["sender"] = frappe.session.user_email;
			}
		}

		return fields;
	}

	get_content_field() {
		if (this.dialog.fields_dict.use_html.value) {
			return this.dialog.fields_dict.html_content;
		} else {
			return this.dialog.fields_dict.content;
		}
	}

	get_default_recipients(fieldname) {
		// MultiSelect Pills holds an array of recipients (one pill each).
		if (this.frm?.events.get_email_recipients) {
			return this.frm.events.get_email_recipients(this.frm, fieldname) || [];
		} else {
			return [];
		}
	}

	guess_language() {
		// when attach print for print format changes try to guess language
		// if print format has language then set that else boot lang.

		// Print language resolution:
		// 1. Document's print_language field
		// 2. print format's default field
		// 3. user lang
		// 4. system lang
		// 3 and 4 are resolved already in boot
		let document_lang = this.frm?.doc?.language;
		let print_format = this.dialog.get_value("select_print_format");

		let print_format_lang;
		if (print_format != "Standard") {
			print_format_lang = frappe.get_doc(
				":Print Format",
				print_format
			)?.default_print_language;
		}

		let lang = document_lang || print_format_lang || frappe.boot.lang;
		this.dialog.set_value("print_language", lang);
	}

	async check_email_template_html(email_template) {
		const r = await frappe.db.get_value("Email Template", email_template, "use_html");
		// Show or hide "Use HTML" based on the Email Template's use_html value
		if (r.message?.use_html === 1) {
			// Show the field.
			this.dialog.fields_dict.use_html.toggle(true);
		} else {
			this.hide_use_html_field();
		}
	}

	// Guarded against duplicate applies — onchange can fire more than once for the same
	// value (Frappe field refresh, awesomplete blur), which would otherwise append twice.
	apply_email_template(template_name) {
		if (!template_name || this.last_applied_template === template_name) return;
		this.last_applied_template = template_name;
		frappe.call({
			method: "frappe.email.doctype.email_template.email_template.get_email_template",
			args: {
				template_name,
				doc: this.doc,
				sender: this.dialog.get_value("sender") || "",
			},
			callback: (r) => {
				if (!r || !r.message) return;
				const content_field = this.get_content_field();
				const subject_field = this.dialog.fields_dict.subject;
				const existing = content_field.get_value() || "";
				content_field.set_value(r.message.message + existing);
				subject_field.set_value(r.message.subject);
			},
		});
	}

	hide_use_html_field() {
		this.dialog.fields_dict.use_html.set_input(false); // reset the value
		this.dialog.fields_dict.use_html.toggle(false); // hide the field
	}

	prepare() {
		this.setup_multiselect_queries();
		this.setup_recipient_pills();
		this.setup_subject_and_recipients();
		this.setup_print();
		this.setup_attach();
		this.setup_email();
		this.setup_last_edited_communication();
		this.setup_add_signature_button();
		this.set_values();
	}

	setup_add_signature_button() {
		let has_sender = this.dialog.has_field("sender");
		this.dialog.set_df_property("add_signature", "hidden", !has_sender);
	}

	setup_multiselect_queries() {
		["recipients", "cc", "bcc"].forEach((field) => {
			this.dialog.fields_dict[field].get_data = () => {
				// Pills commit selected values, so the text being typed lives in the
				// raw input (get_value() now returns the committed array).
				const control = this.dialog.fields_dict[field];
				const txt = (control.$input?.val() || "").trim();
				const args = { txt };

				if (this.frm?.events.get_email_recipient_filters) {
					args.extra_filters = this.frm.events.get_email_recipient_filters(
						this.frm,
						field
					);
				}

				frappe.call({
					method: "frappe.email.get_contact_list",
					args: args,
					callback: (r) => {
						this.dialog.fields_dict[field].set_data(r.message);
					},
				});
			};
		});
	}

	setup_recipient_pills() {
		// get_pill_html runs with `this` bound to the control, so keep a handle on
		// the composer for the shared avatar cache.
		const me = this;
		this._recipient_avatars = this._recipient_avatars || {};

		["recipients", "cc", "bcc"].forEach((fieldname) => {
			const control = this.dialog.fields_dict[fieldname];
			if (!control) return;

			// Accept comma/semicolon/newline-separated strings (defaults, reply-all
			// prefill, server values) as well as arrays, splitting into deduped rows
			// so the string-based recipient logic elsewhere keeps working.
			control.parse = function (value) {
				if (Array.isArray(value)) return value;
				this.rows = this.rows || [];
				if (value) {
					String(value)
						.split(/[,;\n]/)
						.map((email) => email.trim())
						.filter(Boolean)
						.forEach((email) => {
							if (!this.rows.includes(email)) this.rows.push(email);
						});
				}
				return this.rows;
			};

			// Chip = the Espresso tag (`.es-badge` with a removable suffix), same
			// component the form sidebar uses for document tags, with an avatar
			// (photo if the recipient is a known user, else initials) prefixed.
			control.get_pill_html = function (value) {
				const $tag = frappe.ui.badge({
					label: this.get_label(value) || value,
					size: "lg",
					icon_right: "x",
					title: value,
					css_class: "email-composer-recipient-tag tb-selected-value",
					attrs: { "data-value": encodeURIComponent(value) },
				});
				// Photo from the matching Contact (or User) when we have one; otherwise
				// frappe.avatar falls back to the initial. Passing `null` as the user
				// keeps it off frappe.user_info, which only knows desk users.
				const photo = me._recipient_avatars?.[String(value).toLowerCase()] || null;
				$tag.prepend(
					frappe.avatar(
						photo ? null : value,
						"avatar avatar-xs email-composer-tag-avatar",
						value,
						photo
					)
				);
				// wrap the label text so it can ellipsize — a bare text node in a flex
				// container can't (same wrap the sidebar tag does)
				$tag.contents()
					.filter(
						(_, node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
					)
					.wrap('<span class="pill-label ellipsis"></span>');
				$tag.find(".es-badge__affix").attr({
					role: "button",
					tabindex: 0,
					"aria-label": __("Remove"),
				});
				return $tag[0].outerHTML;
			};

			// Remove on MOUSEDOWN, not click. A click on the × used to blur the input,
			// which scheduled a collapse; on anything but a quick tap the collapse fired
			// between mousedown and mouseup, hid the chip under the cursor and the click
			// event never landed — so only the chips that stay visible when collapsed
			// (the first ones) could be removed. preventDefault() also keeps focus in the
			// input, so nothing re-collapses while the user is clearing chips.
			control.$multiselect_wrapper.on("mousedown", ".es-badge__affix", (e) => {
				e.preventDefault();
				this.remove_recipient(control, $(e.currentTarget).closest(".tb-selected-value"));
			});
			control.$multiselect_wrapper.on("keydown", ".es-badge__affix", (e) => {
				if (e.key !== "Enter" && e.key !== " ") return;
				e.preventDefault();
				this.remove_recipient(control, $(e.currentTarget).closest(".tb-selected-value"));
			});

			// An address typed by hand (not picked from the dropdown) commits through
			// ControlAutocomplete's Enter/blur path, which never clears the raw input —
			// only "awesomplete-selectcomplete" does, and that fires for dropdown picks
			// only. The address was left sitting as text beside its own chip, and the
			// next one typed would concatenate onto it. Only clear once the value has
			// actually landed in `rows`, so text that failed to commit is kept.
			const clear_committed_text = () => {
				const typed = (control.$input?.val() || "").trim();
				if (typed && (control.rows || []).includes(typed)) {
					control.$input.val("");
				}
			};

			// Clear in the SAME task that renders the pill, not a deferred one: a
			// setTimeout here let the browser paint a frame with the chip and the
			// leftover text both visible, which flashed on the first address typed.
			const render_pills = control.set_formatted_input.bind(control);
			control.set_formatted_input = function (value) {
				render_pills(value);
				clear_committed_text();
				me.fetch_recipient_avatars(control);
			};
			control.$input?.on("keydown", (e) => {
				if (e.key === "Enter") clear_committed_text();
			});

			// Collapse to the first two chips + "+N more" when the field is blurred;
			// the whole field is a click target that expands to all chips.
			control.$input?.on("focus", () => {
				clearTimeout(control._collapse_timer);
				this.expand_recipient_row(control);
			});
			control.$input?.on("blur", () => {
				clear_committed_text();
				clearTimeout(control._collapse_timer);
				control._collapse_timer = setTimeout(
					() => this.collapse_recipient_row(control),
					150
				);
			});
			control.$multiselect_wrapper?.on("click", (e) => {
				if (!control.$multiselect_wrapper.hasClass("is-collapsed")) return;
				if ($(e.target).closest(".tb-selected-value").length) return; // chip/× → leave it
				this.expand_recipient_row(control);
				control.$input?.focus(); // caret at end
			});
		});
	}

	// Resolve real photos for the addresses currently in a recipient field, then
	// repaint that field's chips once. Every looked-up address is cached — including
	// the ones with no photo, stored as null — so a given address is only ever
	// requested once and the repaint can't feed back into another lookup.
	fetch_recipient_avatars(control) {
		const cache = (this._recipient_avatars = this._recipient_avatars || {});
		const pending = (control.rows || [])
			.map((row) => String(row).toLowerCase())
			.filter((email) => email && !(email in cache));
		if (!pending.length) return;

		// claim them up front so a second render mid-flight doesn't re-request
		pending.forEach((email) => (cache[email] = null));

		frappe.call({
			method: "frappe.email.get_recipient_avatars",
			args: { emails: pending },
			callback: (r) => {
				const found = r.message || {};
				if (!Object.keys(found).length) return;
				Object.assign(cache, found);
				// repaint with the photos now in hand; set_pill_html is the raw
				// renderer, so this can't re-enter the wrapped set_formatted_input
				control.set_pill_html(control.rows || []);
			},
		});
	}

	remove_recipient(control, $tag) {
		const value = decodeURIComponent($tag.attr("data-value") || "");
		if (!value) return;
		control.rows = (control.rows || []).filter((row) => row !== value);
		// repaint first, then sync the Dialog's value, so the row never renders
		// against a stale `rows`
		control.set_pill_html(control.rows);
		control.parse_validate_and_set_in_model("");

		// set_pill_html only touches the chips — the "+N more" badge from the last
		// collapse is now stale (it counted the row we just removed) and every chip
		// it just redrew is visible again, so recompute the collapse from scratch.
		// collapse_recipient_row bails on its own while the input is still focused
		// (removal keeps focus in place), leaving everything visible until blur.
		control.$multiselect_wrapper.find(".email-composer-more-count").remove();
		this.collapse_recipient_row(control);
	}

	expand_recipient_row(control) {
		const $wrapper = control.$multiselect_wrapper;
		if (!$wrapper?.length) return;
		clearTimeout(control._collapse_timer);
		$wrapper.removeClass("is-collapsed");
		$wrapper.find(".email-composer-more-count").remove();
		$wrapper.find(".tb-selected-value").removeClass("hidden");
		// NB: do NOT focus here — the focus handler calls this, so focusing would
		// recurse infinitely. The click-to-expand path focuses explicitly instead.
	}

	collapse_recipient_row(control) {
		const $wrapper = control.$multiselect_wrapper;
		if (!$wrapper?.length) return;
		// Still editing (e.g. refocused after choosing a suggestion) — don't collapse.
		if (control.$input?.is(":focus")) return;
		if ($wrapper[0].contains(document.activeElement)) return;
		// Pointer is over the row: collapsing would pull chips out from under the
		// cursor mid-click. Wait for the pointer to leave.
		if ($wrapper.is(":hover")) return;

		$wrapper.find(".email-composer-more-count").remove();
		const $tags = $wrapper.find(".tb-selected-value").removeClass("hidden");
		if (!$tags.length) {
			$wrapper.removeClass("is-collapsed");
			return;
		}
		// Not laid out yet — measuring now would hide everything.
		if ($wrapper.width() < 40) return;

		// Show exactly the first two chips; collapse the rest into "+N more".
		$wrapper.addClass("is-collapsed");
		const VISIBLE = 2;
		if ($tags.length <= VISIBLE) return;

		$tags.slice(VISIBLE).addClass("hidden");
		$wrapper.append(
			frappe.ui.badge.html({
				label: __("+{0} more", [$tags.length - VISIBLE]),
				size: "lg",
				variant: "ghost",
				css_class: "email-composer-more-count",
			})
		);
	}

	setup_recipients_if_reply() {
		if (!this.is_a_reply || !this.last_email) return;
		let sender = this.dialog.get_value("sender");
		if (!sender) return;
		const fields = {
			recipients: this.dialog.fields_dict.recipients,
			cc: this.dialog.fields_dict.cc,
			bcc: this.dialog.fields_dict.bcc,
		};
		// If same user replies to their own email, set recipients to last email recipients
		if (this.last_email.sender == sender) {
			fields.recipients.set_value(this.last_email.recipients);
			if (this.reply_all) {
				fields.cc.set_value(this.last_email.cc);
				fields.bcc.set_value(this.last_email.bcc);
			}
		} else {
			fields.recipients.set_value(this.last_email.sender);
			if (this.reply_all) {
				// if sending reply add ( last email's recipients - sender's email_id ) to cc.
				const recipients = this.last_email.recipients.split(",").map((r) => r.trim());
				if (!this.cc) {
					this.cc = "";
				}
				const cc_array = this.cc.split(",").map((r) => r.trim());
				if (this.cc && !this.cc.endsWith(", ")) {
					this.cc += ", ";
				}
				this.cc += recipients
					.filter((r) => !cc_array.includes(r) && r != sender)
					.join(", ");
				this.cc = this.cc.replace(sender + ", ", "");
				fields.cc.set_value(this.cc);
			}
		}
	}

	setup_subject_and_recipients() {
		this.subject = this.subject || "";

		if (!this.forward && !this.recipients && this.last_email) {
			this.recipients = this.last_email.sender;
			// If same user replies to their own email, set recipients to last email recipients
			if (this.last_email.sender == this.sender) {
				this.recipients = this.last_email.recipients;
			}

			if (this.reply_all) {
				this.cc = this.last_email.cc;
				this.bcc = this.last_email.bcc;
			}
		}

		if (!this.forward && !this.recipients) {
			this.recipients = this.frm && this.frm.timeline.get_recipient();
		}

		if (!this.subject && this.frm) {
			// get subject from last communication
			const last = this.frm.timeline.get_last_email();

			if (last) {
				this.subject = last.subject;
				if (!this.recipients) {
					this.recipients = last.sender;
				}

				// prepend "Re:"
				if (strip(this.subject.toLowerCase().split(":")[0]) != "re") {
					this.subject = __("Re: {0}", [this.subject]);
				}
			}

			if (!this.subject) {
				this.subject = this.frm.doc.name;
				if (this.frm.meta.subject_field && this.frm.doc[this.frm.meta.subject_field]) {
					this.subject = this.frm.doc[this.frm.meta.subject_field];
				} else if (this.frm.meta.title_field && this.frm.doc[this.frm.meta.title_field]) {
					this.subject = this.frm.doc[this.frm.meta.title_field];
				}
			}

			// always add an identifier to catch a reply
			// some email clients (outlook) may not send the message id to identify
			// the thread. So as a backup we use the name of the document as identifier
			const identifier = `#${this.frm.doc.name}`;

			// converting to str for int names
			if (!cstr(this.subject).includes(identifier)) {
				this.subject = `${this.subject} (${identifier})`;
			}
		}

		if (this.frm && !this.recipients) {
			this.recipients = this.frm.doc[this.frm.email_field];
		}
	}

	setup_last_edited_communication() {
		if (this.frm) {
			this.doctype = this.frm.doctype;
			this.key = this.frm.docname;
		} else {
			this.doctype = this.key = "Inbox";
		}

		if (this.last_email) {
			this.key = this.key + ":" + this.last_email.name;
		}

		if (this.subject) {
			this.key = this.key + ":" + this.subject;
		}

		this.dialog.on_hide = () => {
			$.extend(this.get_last_edited_communication(true), this.dialog.get_values(true));

			if (this.frm) {
				$(document).trigger("form-stopped-typing", [this.frm]);
			}
		};
	}

	get_last_edited_communication(clear) {
		if (!frappe.last_edited_communication[this.doctype]) {
			frappe.last_edited_communication[this.doctype] = {};
		}

		if (clear || !frappe.last_edited_communication[this.doctype][this.key]) {
			frappe.last_edited_communication[this.doctype][this.key] = {};
		}

		return frappe.last_edited_communication[this.doctype][this.key];
	}

	async set_values() {
		for (const fieldname of ["recipients", "cc", "bcc", "sender"]) {
			await this.dialog.set_value(fieldname, this[fieldname] || "");
		}

		const subject = this.subject ? frappe.utils.html2text(this.subject) : "";
		await this.dialog.set_value("subject", subject);

		await this.set_values_from_last_edited_communication();
		await this.set_content();

		// set default email template for the first email in a document
		if (this.frm && !this.is_a_reply && !this.content_set) {
			const email_template = this.frm.meta.default_email_template || "";
			await this.dialog.set_value("email_template", email_template);
		}

		// Reveal CC/BCC rows (and mark their toggle active) when values are
		// pre-filled, e.g. reply-all.
		if (this.$composer) {
			for (const type of ["cc", "bcc"]) {
				if (this.dialog.get_value(type)) {
					this.$composer.find(`.email-composer-${type}-row`).removeClass("hidden");
					this.$composer
						.find(`.email-composer-toggle[data-target="${type}"]`)
						.addClass("active");
				}
			}
		}
	}

	async set_values_from_last_edited_communication() {
		if (this.message) return;

		const last_edited = this.get_last_edited_communication();
		if (!last_edited.content && !last_edited.html_content) return;

		// For replies: strip duplicate quoted content (Quill uses <p>---</p>)
		if (this.is_a_reply) {
			const reply_block = this.get_earlier_reply();
			for (const field of ["content", "html_content"]) {
				if (last_edited[field]) {
					last_edited[field] =
						(last_edited[field].split(separator_regex)[0] || "").trimEnd() +
						reply_block;
				}
			}
		}

		// prevent re-triggering of email template
		if (last_edited.email_template) {
			const template_field = this.dialog.fields_dict.email_template;
			await template_field.set_model_value(last_edited.email_template);
			await this.check_email_template_html(last_edited.email_template);
			delete last_edited.email_template;
		}

		await this.dialog.set_values(last_edited);
		this.content_set = true;
	}

	selected_format() {
		return (
			this.dialog.fields_dict.select_print_format.input.value ||
			(this.frm && this.frm.meta.default_print_format) ||
			"Standard"
		);
	}

	get_print_format(format) {
		if (!format) {
			format = this.selected_format();
		}

		if (locals[":Print Format"] && locals[":Print Format"][format]) {
			return locals[":Print Format"][format];
		} else {
			return {};
		}
	}

	// "Standard • Frappe 2024 • English" — the three print settings, read straight
	// off the dialog's own fields so the card can never disagree with what gets
	// sent. Language resolves to its readable name asynchronously (the field holds
	// a code like "en"); the code shows until it lands, and stays if the lookup
	// fails.
	render_print_card_meta() {
		const $meta = this.$composer?.find(".email-composer-print-card__meta");
		if (!$meta?.length) return;

		const fields = this.dialog.fields_dict;
		const lang = fields.print_language?.get_value() || "";
		const parts = [
			fields.select_print_format?.get_value(),
			fields.select_letter_head?.get_value(),
			this._language_labels?.[lang] || lang,
		];
		$meta.text(parts.filter(Boolean).join(" • "));

		if (!lang || this._language_labels?.[lang]) return;
		this._language_labels = this._language_labels || {};
		frappe.db
			.get_value("Language", lang, "language_name")
			.then(({ message }) => {
				if (!message?.language_name) return;
				this._language_labels[lang] = message.language_name;
				this.render_print_card_meta();
			})
			.catch(() => {});
	}

	// Preview the document print exactly as it will be attached — same format,
	// letter head and language the card shows. Uses /printview rather than
	// frappe.utils.print, which appends trigger_print=1 and would fire the
	// browser's print dialog instead of just showing the document.
	open_print_preview() {
		if (!this.frm) return;

		const fields = this.dialog.fields_dict;
		const params = {
			doctype: this.frm.doctype,
			name: this.frm.docname,
			format: fields.select_print_format?.get_value() || "Standard",
			_lang: fields.print_language?.get_value() || frappe.boot.lang,
		};

		// letterhead is optional: an empty picker means "no letter head", which
		// printview expresses with no_letterhead rather than an empty letterhead.
		const letterhead = fields.select_letter_head?.get_value();
		if (letterhead) {
			params.letterhead = letterhead;
		} else {
			params.no_letterhead = 1;
		}

		const query = Object.entries(params)
			.map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
			.join("&");
		window.open(frappe.urllib.get_full_url(`/printview?${query}`), "_blank");
	}

	// Edit (pencil) on the print card. Mirrors the three fields the original
	// inline UI exposed — print format, letter head, print language — and writes
	// straight back to them, so send_action keeps reading the same values it
	// always did.
	open_print_settings() {
		const fields = this.dialog.fields_dict;
		const print_formats = this.frm ? frappe.meta.get_print_formats(this.frm.meta.name) : [];

		const settings = new frappe.ui.Dialog({
			title: __("Print format"),
			fields: [
				{
					label: __("Print Format"),
					fieldname: "print_format",
					fieldtype: "Select",
					options: print_formats,
					default: fields.select_print_format?.get_value(),
				},
				{
					label: __("Letter Head"),
					fieldname: "letter_head",
					fieldtype: "Link",
					options: "Letter Head",
					default: fields.select_letter_head?.get_value(),
				},
				{
					label: __("Print Language"),
					fieldname: "print_language",
					fieldtype: "Link",
					options: "Language",
					default: fields.print_language?.get_value(),
				},
			],
			primary_action_label: __("Save"),
			// set_value is async — await all three before repainting, or the card's
			// meta line reads the previous values and goes stale against what will
			// actually be sent.
			primary_action: async (values) => {
				await this.dialog.set_value("select_print_format", values.print_format || "");
				await this.dialog.set_value("select_letter_head", values.letter_head || "");
				await this.dialog.set_value("print_language", values.print_language || "");
				settings.hide();
				this.render_print_card_meta();
				this.sync_print_menu?.();
			},
		});
		settings.show();
	}

	setup_print() {
		// print formats
		const fields = this.dialog.fields_dict;

		// toggle print format and letter head
		$(fields.attach_document_print.input).click(function () {
			const checked = $(this).prop("checked");
			$(fields.select_print_format.wrapper).toggle(checked);
			$(fields.select_letter_head.wrapper).toggle(checked);
		});

		// select print format
		$(fields.select_print_format.wrapper).toggle(false);
		$(fields.select_letter_head.wrapper).toggle(false);

		if (this.frm) {
			const print_formats = frappe.meta.get_print_formats(this.frm.meta.name);
			$(fields.select_print_format.input)
				.empty()
				.add_options(print_formats)
				.val(print_formats[0]);
			this.set_default_letterhead();
		} else {
			$(fields.attach_document_print.wrapper).toggle(false);
		}
		this.guess_language();
	}

	set_default_letterhead() {
		const fields = this.dialog.fields_dict;
		if (this.frm.doc?.letter_head) {
			this.dialog.set_value("select_letter_head", this.frm.doc.letter_head);
			return;
		}
		frappe.db
			.get_value("Letter Head", { disabled: 0, is_default: 1 }, "name")
			.then(({ message }) => {
				if (message?.name) {
					this.dialog.set_value("select_letter_head", message.name);
				}
			})
			.catch((err) => console.error("Failed to fetch default Letter Head:", err));
	}

	setup_attach() {
		const fields = this.dialog.fields_dict;
		const attach = $(fields.select_attachments.wrapper);

		if (!this.attachments) {
			this.attachments = [];
		}

		let args = {
			folder: "Home/Attachments",
			on_success: (attachment) => {
				this.attachments.push(attachment);
				this.render_attachment_rows(attachment);
			},
		};

		if (this.frm) {
			args = {
				doctype: this.frm.doctype,
				docname: this.frm.docname,
				folder: "Home/Attachments",
				on_success: (attachment) => {
					this.frm.attachments.attachment_uploaded(attachment);
					this.render_attachment_rows(attachment);
				},
			};
		}

		$(`
			<label class="control-label">
				${__("Select Attachments")}
			</label>
			<div class='attach-list'></div>
			<p class='add-more-attachments'>
				<button class='btn btn-xs btn-default'>
					${frappe.utils.icon("plus", "xs")}&nbsp;
					${__("Add Attachment")}
				</button>
			</p>
		`).appendTo(attach.empty());

		attach
			.find(".add-more-attachments button")
			.on("click", () => new frappe.ui.FileUploader(args));
		this.render_attachment_rows();
	}

	// Every attachment available to this email: whatever is already on the
	// document, plus anything uploaded from inside the composer.
	get_available_attachments() {
		let files = [];
		if (this.attachments?.length) files = files.concat(this.attachments);
		if (this.frm) files = files.concat(this.frm.get_files());

		const seen = new Set();
		return files.filter((f) => {
			if (!f?.file_name || seen.has(f.name)) return false;
			seen.add(f.name);
			return true;
		});
	}

	// A chip is rendered only for an attachment the user actually picked, and each
	// chip carries the hidden checked input that send_action collects. Nothing is
	// attached implicitly — the document's own files have to be chosen first.
	render_attachment_rows(attachment) {
		const attachment_rows = $(this.dialog.fields_dict.select_attachments.wrapper).find(
			".attach-list"
		);
		this.selected_attachments = this.selected_attachments || new Set();

		// a file uploaded from the composer is an explicit choice — select it
		if (attachment?.name) this.selected_attachments.add(attachment.name);

		attachment_rows.empty();
		this.get_available_attachments().forEach((f) => {
			if (!this.selected_attachments.has(f.name)) return;
			f.file_url = frappe.urllib.get_full_url(f.file_url);
			attachment_rows.append(this.get_attachment_row(f));
		});
	}

	// One row of the attachment picker: checkbox, a thumbnail (or a type tile),
	// then the file name over "TYPE · size" — the whole row is the label, so
	// clicking anywhere on it toggles the box.
	get_file_picker_row(file) {
		const name = file.file_name || "";
		const source = file.file_url || name;
		const is_image = frappe.utils.is_image_file(source);
		const extension = (name.split(".").pop() || "").toUpperCase();

		let type_label = extension;
		if (is_image) type_label = __("Image");
		else if (frappe.utils.is_video_file(source)) type_label = __("Video");

		const size = file.file_size ? frappe.form.formatters.FileSize(file.file_size) : "";
		const meta = [type_label, size].filter(Boolean).join(" · ");

		const $row = $(`
			<label class="email-composer-file-row">
				<input type="checkbox" class="email-composer-file-row__check">
				<span class="email-composer-file-row__thumb" data-ext="${frappe.utils.escape_html(
					extension
				)}"></span>
				<span class="email-composer-file-row__text">
					<span class="email-composer-file-row__name ellipsis"></span>
					<span class="email-composer-file-row__meta ellipsis"></span>
				</span>
			</label>
		`);

		$row.attr("title", name);
		$row.find(".email-composer-file-row__name").text(name);
		$row.find(".email-composer-file-row__meta").text(meta);
		$row.find("input")
			.prop("checked", this.selected_attachments.has(file.name))
			.data("file", file.name);

		const $thumb = $row.find(".email-composer-file-row__thumb");
		if (is_image) {
			// CSS-escape the url so quotes/parens in a filename can't break out
			$thumb.addClass("is-image").css("background-image", `url("${CSS.escape(source)}")`);
		} else {
			$thumb.text(extension.slice(0, 4));
			if (extension === "PDF") $thumb.addClass("is-pdf");
		}
		return $row;
	}

	// "Select attachments" — the old checkbox list, now in its own dialog.
	open_attachment_picker() {
		const available = this.get_available_attachments();
		if (!available.length) {
			frappe.msgprint({
				title: __("No attachments"),
				message: __("This document has no files to attach yet."),
				indicator: "orange",
			});
			return;
		}

		this.selected_attachments = this.selected_attachments || new Set();

		// Build the dialog once and reuse it — a fresh frappe.ui.Dialog per open
		// leaves the previous one in the DOM, so repeated opens pile up copies.
		if (!this.attachment_picker) {
			this.attachment_picker = new frappe.ui.Dialog({
				title: __("Select attachments"),
				fields: [{ fieldtype: "HTML", fieldname: "files" }],
				primary_action_label: __("Attach"),
				primary_action: () => {
					const $rows = this.attachment_picker.fields_dict.files.$wrapper;
					$rows.find("input").each((_, cb) => {
						const file = $(cb).data("file");
						if (cb.checked) this.selected_attachments.add(file);
						else this.selected_attachments.delete(file);
					});
					this.attachment_picker.hide();
					this.render_attachment_rows();
				},
			});
		}

		// repopulate every time: files can be uploaded between opens
		const $list = $(`<div class="email-composer-file-picker"></div>`);
		available.forEach((f) => $list.append(this.get_file_picker_row(f)));
		this.attachment_picker.fields_dict.files.$wrapper.empty().append($list);
		this.attachment_picker.show();
	}

	get_attachment_row(attachment, checked) {
		// Hidden checkbox carries data-file-name so send_action's `[data-file-name]:checked`
		// selector still finds it — removing the row drops the checkbox with it.
		// .email-composer-attach-pill avoids the form-sidebar .attachment-row overrides that strip
		// the pill background.
		const $row = $(`<div class="email-composer-attach-pill" title="${attachment.file_name}">
			<input
				type="checkbox"
				data-file-name="${attachment.name}"
				${checked === false ? "" : "checked"}
				hidden
			>
		</div>`);
		const size = attachment.file_size
			? frappe.form.formatters.FileSize(attachment.file_size)
			: null;
		const label = size ? `${attachment.file_name} (${size})` : attachment.file_name;
		const icon = frappe.utils.icon("link", "xs");
		const $pill = frappe.get_data_pill(
			label,
			attachment.name,
			() => {
				// drop it from the selection too, or the next re-render brings it back
				this.selected_attachments?.delete(attachment.name);
				$row.remove();
			},
			icon,
			false,
			"xs"
		);
		return $row.append($pill);
	}

	setup_email() {
		// email
		const fields = this.dialog.fields_dict;

		if (this.attach_document_print) {
			$(fields.attach_document_print.input).click();
			$(fields.select_print_format.wrapper).toggle(true);
		}

		$(fields.send_me_a_copy.input).on("click", () => {
			// update send me a copy (make it sticky)
			const val = fields.send_me_a_copy.get_value();
			frappe.db.set_value("User", frappe.session.user, "send_me_a_copy", val);
			frappe.boot.user.send_me_a_copy = val;
		});
	}

	send_action() {
		const me = this;
		const btn = me.dialog.get_primary_btn();
		const form_values = this.get_values();
		if (!form_values) return;

		// NB: `dialog.wrapper` is NOT the modal — Layout.make() overwrites Dialog's
		// own assignment with its `.form-layout` div. render_composer_layout()
		// moves every control out of that div into the composer skeleton, so
		// searching it finds nothing and no attachment is ever sent. Search the
		// modal root, which holds the relocated controls either way.
		const selected_attachments = $.map(
			me.dialog.$wrapper.find("[data-file-name]:checked"),
			function (element) {
				return $(element).attr("data-file-name");
			}
		);

		if (form_values.attach_document_print) {
			me.send_email(
				btn,
				form_values,
				selected_attachments,
				null,
				form_values.select_print_format || "",
				form_values.select_letter_head || null
			);
		} else {
			me.send_email(btn, form_values, selected_attachments);
		}
	}

	get_values() {
		const form_values = this.dialog.get_values();

		// Recipient fields are MultiSelect Pills, so recipients/cc/bcc are arrays.
		for (let i = 0, l = this.dialog.fields.length; i < l; i++) {
			const df = this.dialog.fields[i];

			if (df.is_cc_checkbox) {
				// concat the doc field into cc / bcc
				if (form_values[df.fieldname]) {
					form_values.cc = [].concat(form_values.cc || [], df.fieldname);
					form_values.bcc = [].concat(form_values.bcc || [], df.fieldname);
				}

				delete form_values[df.fieldname];
			}
		}

		// The send RPC (communication.email.make) expects comma-separated strings.
		["recipients", "cc", "bcc"].forEach((field) => {
			if (Array.isArray(form_values[field])) {
				form_values[field] = form_values[field].join(", ");
			}
		});

		return form_values;
	}

	save_as_draft() {
		if (this.dialog && this.frm) {
			let message = this.get_email_content();
			message = message.split(separator_regex)[0];
			this.save_item_in_local_forage(this.frm.doctype + this.frm.docname, message);
			this.save_item_in_local_forage(
				this.frm.doctype + this.frm.docname + "_use_html",
				this.dialog.get_value("use_html")
			);
		}
	}

	save_item_in_local_forage(key, value) {
		localforage.setItem(key, value).catch((e) => {
			if (e) {
				// silently fail
				console.log(e);
				console.warn("[Communication] IndexedDB is full. Cannot save communication draft"); // eslint-disable-line
			}
		});
	}

	clear_cache() {
		this.delete_saved_draft();
		this.get_last_edited_communication(true);
	}

	delete_saved_draft() {
		if (this.dialog && this.frm) {
			localforage.removeItem(this.frm.doctype + this.frm.docname).catch((e) => {
				if (e) {
					// silently fail
					console.log(e);
					console.warn(
						"[Communication] IndexedDB is full. Cannot save message as draft"
					);
				}
			});
		}
	}

	send_email(btn, form_values, selected_attachments, print_html, print_format, letterhead) {
		const me = this;
		this.dialog.hide();

		if (!form_values.recipients && !form_values.cc && !form_values.bcc) {
			frappe.msgprint(__("Enter Email Recipient(s) in the To, CC, or BCC fields"));
			return;
		}

		if (!form_values.attach_document_print) {
			print_html = null;
			print_format = null;
		}

		if (this.frm && !frappe.model.can_email(this.doc.doctype, this.frm)) {
			frappe.msgprint(__("You are not allowed to send emails related to this document"));
			return;
		}

		return frappe.call({
			method: "frappe.core.doctype.communication.email.make",
			args: {
				recipients: form_values.recipients,
				cc: form_values.cc,
				bcc: form_values.bcc,
				subject: form_values.subject,
				content: me.get_email_content(),
				doctype: me.doc.doctype,
				name: me.doc.name,
				send_email: 1,
				print_html: print_html,
				send_me_a_copy: form_values.send_me_a_copy,
				print_format: print_format,
				sender: form_values.sender,
				sender_full_name: form_values.sender ? frappe.user.full_name() : undefined,
				email_template: form_values.email_template,
				attachments: selected_attachments,
				read_receipt: form_values.send_read_receipt,
				print_letterhead: me.is_print_letterhead_checked(),
				letterhead: letterhead || null,
				send_after: form_values.send_after ? form_values.send_after : null,
				print_language: form_values.print_language,
				raw_html: form_values.use_html,
				add_css: form_values.add_css,
				in_reply_to: (this.is_a_reply && this.last_email?.name) || null,
			},
			btn,
			callback(r) {
				if (!r.exc) {
					frappe.utils.play_sound("email");

					const communication_name = r.message["name"];

					if (r.message["emails_not_sent_to"]) {
						frappe.msgprint(
							__("Email not sent to {0} (unsubscribed / disabled)", [
								frappe.utils.escape_html(r.message["emails_not_sent_to"]),
							])
						);
					}

					me.clear_cache();

					if (me.frm) {
						me.frm.reload_doc();
					}

					const undo_toast = frappe.ui.toast({
						message: __("Email Sent"),
						type: "success",
						duration: 10000,
						action: {
							label: __("Undo"),
							onclick: () => {
								undo_toast.dismiss();
								frappe
									.xcall(
										"frappe.core.doctype.communication.email.undo_email_send",
										{ communication_name: communication_name }
									)
									.then((d) => {
										if (me.frm) {
											me.frm.reload_doc();
										}

										// Reopen the composer with the recovered data
										new frappe.views.CommunicationComposer({
											doc: d.doc,
											subject: d.subject,
											recipients: d.recipients,
											cc: d.cc,
											bcc: d.bcc,
											message: d.content,
											sender: d.sender,
											read_receipt: d.send_read_receipt,
											attachments: d.attachments,
											frm: me.frm,
										});

										frappe.ui.toast({
											message: __("Email sending undone"),
											type: "info",
										});
									});
							},
						},
					});

					// try the success callback if it exists
					if (me.success) {
						try {
							me.success(r);
						} catch (e) {
							console.log(e);
						}
					}
				} else {
					frappe.msgprint(
						__("There were errors while sending email. Please try again.")
					);

					// try the error callback if it exists
					if (me.error) {
						try {
							me.error(r);
						} catch (e) {
							console.log(e);
						}
					}
				}
			},
		});
	}

	is_print_letterhead_checked() {
		if (this.frm && $(this.frm.wrapper).find(".form-print-wrapper").is(":visible")) {
			return $(this.frm.wrapper).find(".print-letterhead").prop("checked") ? 1 : 0;
		} else {
			return (
				frappe.model.get_doc(":Print Settings", "Print Settings") || { with_letterhead: 1 }
			).with_letterhead
				? 1
				: 0;
		}
	}

	async set_content(sender_email) {
		if (this.content_set) return;

		let message = this.message || "";
		if (!message && this.frm) {
			const { doctype, docname } = this.frm;
			message = (await localforage.getItem(doctype + docname)) || "";
			const use_html = (await localforage.getItem(doctype + docname + "_use_html")) || 0;
			await this.dialog.set_value("use_html", use_html);
		}

		if (message) {
			this.content_set = true;
		}

		const signature = await this.get_signature(sender_email || "");
		if (!this.content_set || !strip_html(message).includes(strip_html(signature))) {
			message += signature;
		}

		if (this.is_a_reply && !this.reply_set) {
			message = message.split(separator_regex)[0] + this.get_earlier_reply();
		}

		await this.set_email_content(message);
	}

	async get_signature(sender_email) {
		let signature = frappe.boot.user.email_signature;

		if (!signature) {
			let filters = {
				add_signature: 1,
			};

			if (sender_email) {
				filters["email_id"] = sender_email;
			} else {
				filters["default_outgoing"] = 1;
			}

			const email_accounts = await frappe.db.get_list("Email Account", {
				filters: filters,
				fields: ["signature", "email_id"],
				limit: 1,
			});

			let filtered_email = null;
			if (email_accounts.length) {
				signature = email_accounts[0].signature;
				filtered_email = email_accounts[0].email_id;
			}

			if (!sender_email && filtered_email) {
				if (
					this.user_email_accounts &&
					this.user_email_accounts.includes(filtered_email)
				) {
					this.dialog.set_value("sender", filtered_email);
				}
			}
		}

		if (!signature) return "";

		if (!frappe.utils.is_html(signature)) {
			signature = signature.replace(/\n/g, "<br>");
		}

		return "<br>" + signature;
	}

	get_earlier_reply() {
		this.reply_set = false;

		const last_email = this.last_email || (this.frm && this.frm.timeline.get_last_email(true));

		if (!last_email) return "";
		let last_email_content = last_email.original_comment || last_email.content;

		// convert the email context to text as we are enclosing
		// this inside <blockquote>
		last_email_content = this.html2text(last_email_content).replace(/\n/g, "<br>");

		// clip last email for a maximum of 20k characters
		// to prevent the email content from getting too large
		if (last_email_content.length > 20 * 1024) {
			last_email_content += "<div>" + __("Message clipped") + "</div>" + last_email_content;
			last_email_content = last_email_content.slice(0, 20 * 1024);
		}

		const communication_date = frappe.datetime.global_date_format(
			last_email.communication_date || last_email.creation
		);

		this.reply_set = true;

		return `
			<div><br></div>
			${separator_element || ""}
			<p>
			${__("On {0}, {1} wrote:", [communication_date, last_email.sender])}
			</p>
			<blockquote>
			${last_email_content}
			</blockquote>
		`;
	}

	html2text(html) {
		// convert HTML to text and try and preserve whitespace

		html = html
			.replace(/<\/div>/g, "<br></div>") // replace end of blocks
			.replace(/<\/p>/g, "<br></p>") // replace end of paragraphs
			.replace(/<br>/g, "\n");

		const text = frappe.utils.html2text(html);
		return text.replace(/\n{3,}/g, "\n\n");
	}

	get_email_content() {
		return this.get_content_field().get_value() || "";
	}

	set_email_content(value) {
		return this.get_content_field().set_value(value);
	}

	on_use_html_toggle(event) {
		if (!event) return;

		this.save_as_draft();
		const use_html = event.target.checked;

		if (use_html) {
			this.dialog.set_value("html_content", this.dialog.get_value("content"));
		} else {
			this.dialog.set_value("content", this.dialog.get_value("html_content"));
		}
	}
};
