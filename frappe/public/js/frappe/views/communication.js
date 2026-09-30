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
		const $wrapper = this.dialog.$wrapper;
		$wrapper.addClass("email-composer-modal");
		$wrapper.attr("data-backdrop", "false");

		this.$fullscreen_btn = $wrapper
			.find(".btn-modal-minimize")
			.removeClass("btn-modal-minimize")
			.off("click")
			.on("click", () => {
				// The expanded styles are guarded with :not(.modal-minimize), so
				// restore first — otherwise this click only flips a dead class.
				if (this.dialog.is_minimized) {
					this.dialog.toggle_minimize();
					$wrapper.addClass("expanded");
				} else {
					$wrapper.toggleClass("expanded");
				}
				this.sync_header_buttons();
			});

		this.$minimize_btn = $(
			frappe.ui.button.html({
				icon: "minus",
				variant: "ghost",
				title: __("Minimize"),
				css_class: "btn-modal-collapse icon-btn",
			})
		).on("click", () => this.dialog.toggle_minimize());
		$wrapper.find(".modal-header .modal-actions").prepend(this.$minimize_btn);
		$wrapper.find(".modal-header .modal-actions .es-button").attr("data-size", "xs");
		// also runs when a click on the title bar restores the composer
		this.dialog.on_minimize_toggle = () => this.sync_header_buttons();
		this.sync_header_buttons();
	}

	sync_header_buttons() {
		const minimized = this.dialog.is_minimized;
		const full = this.dialog.$wrapper.hasClass("expanded") && !minimized;
		const label = full ? __("Exit full screen") : __("Full screen");
		this.$fullscreen_btn
			.attr({ title: label, "aria-label": label })
			.find("use")
			.attr("href", `#icon-${full ? "minimize-2" : "maximize-2"}`);

		const minimize_label = minimized ? __("Restore") : __("Minimize");
		this.$minimize_btn
			.attr({ title: minimize_label, "aria-label": minimize_label })
			.find("use")
			.attr("href", `#icon-${minimized ? "chevron-up" : "minus"}`);
	}

	render_composer_layout() {
		const $body = this.dialog.$body;
		const $original = $body.children();

		this.$composer = $(`
			<div class="email-composer flex flex-col flex-1">
				<div class="email-composer-recipients">
					<div class="email-composer-row email-composer-sender-row hidden flex items-center gap-2 px-4 py-2" data-slot="sender"></div>
					<div class="email-composer-row email-composer-to-row flex items-start gap-2 px-4 py-2">
						<div class="email-composer-to-input flex-1 min-w-0" data-slot="recipients"></div>
						<div class="flex gap-1 shrink-0">
							${frappe.ui.button.html({
								label: __("CC"),
								variant: "ghost",
								css_class: "email-composer-toggle",
								attrs: { "data-target": "cc", "aria-pressed": "false" },
							})}
							${frappe.ui.button.html({
								label: __("BCC"),
								variant: "ghost",
								css_class: "email-composer-toggle",
								attrs: { "data-target": "bcc", "aria-pressed": "false" },
							})}
						</div>
					</div>
					<div class="email-composer-row email-composer-cc-row hidden flex items-start gap-2 px-4 py-2 border-t" data-slot="cc"></div>
					<div class="email-composer-row email-composer-bcc-row hidden flex items-start gap-2 px-4 py-2 border-t" data-slot="bcc"></div>
					<div class="email-composer-row email-composer-subject-row flex items-center gap-3 px-4 py-2 border-t">
						<div class="email-composer-subject flex-1 min-w-0" data-slot="subject"></div>
					</div>
					${frappe.ui.divider.html()}
				</div>
				<div class="email-composer-message-area flex flex-col grow min-h-0 px-4 pt-4 pb-5">
					<div class="flex flex-col flex-1 min-h-0" data-slot="content"></div>
					<div data-slot="html_content"></div>
				</div>
				<div class="email-composer-attachments" data-slot="select_attachments"></div>
				<div class="email-composer-print-format hidden px-4 pb-2"></div>
				<div class="email-composer-footer">
					<div class="email-composer-html-toggle" data-slot="use_html"></div>
					<div class="email-composer-toolbar-slot hidden px-4 py-2"></div>
					<div class="email-composer-banner hidden flex items-center justify-between gap-2 px-4 py-2 bg-surface-gray-1 text-ink-gray-7 text-sm">
						<span class="email-composer-banner__text flex-1"></span>
					</div>
					<div class="flex items-center justify-between gap-2 px-4 py-2 border-t">
						<div class="email-composer-icon-row flex items-center gap-2">
							<div class="dropdown">
								${frappe.ui.button.html({
									icon: "ellipsis",
									variant: "ghost",
									title: __("More options"),
									attrs: { "data-toggle": "dropdown" },
								})}
								<div class="dropdown-menu dropdown-menu-right email-composer-more-menu">
									<div class="dropdown-item email-composer-menu-toggle switch-control" data-action="send-read-receipt" role="switch" tabindex="0" aria-checked="false">
										${frappe.utils.icon("mail-open", "sm")}
										<span>${__("Send read receipt")}</span>
										<span class="switch-visual"><span class="switch-thumb"></span></span>
									</div>
									<div class="dropdown-item email-composer-menu-toggle switch-control" data-action="send-me-a-copy" role="switch" tabindex="0" aria-checked="false">
										${frappe.utils.icon("copy", "sm")}
										<span>${__("Send me a copy")}</span>
										<span class="switch-visual"><span class="switch-thumb"></span></span>
									</div>
								</div>
							</div>
						</div>
						<div class="flex items-center gap-2">
							<div class="email-composer-send-group flex items-center" data-slot="send-button"></div>
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
			"subject",
			"content",
			"html_content",
			"use_html",
			"select_attachments",
		].forEach((fieldname) => {
			const $control = $body.find(`.frappe-control[data-fieldname="${fieldname}"]`);
			if ($control.length) {
				this.$composer.find(`[data-slot="${fieldname}"]`).append($control);
			}
		});

		this.dialog.fields_dict.subject.$input?.attr("placeholder", __("Subject"));

		if (this.user_email_accounts?.length > 1) {
			this.$composer.find(".email-composer-sender-row").removeClass("hidden");
		}

		this.$composer.find(".email-composer-toggle").on("click", (e) => {
			const $btn = $(e.currentTarget);
			const target = $btn.data("target");
			const $row = this.$composer.find(`.email-composer-${target}-row`);
			$row.toggleClass("hidden");
			$btn.attr("aria-pressed", String(!$row.hasClass("hidden")));
			// a closed row must not still send to the addresses hidden in it
			if ($row.hasClass("hidden")) this.dialog.set_value(target, []);
		});

		const fields = this.dialog.fields_dict;
		const send = () => this.$composer.find(".btn-modal-primary").trigger("click");

		const $sendGroup = this.$composer.find('[data-slot="send-button"]');
		const $sendBtn = this.dialog.$wrapper.find(".btn-modal-primary");
		if ($sendBtn.length) {
			$sendGroup.append($sendBtn.addClass("hidden"));
		}
		$sendGroup.append(
			frappe.ui.button({
				label: __("Send"),
				variant: "solid",
				css_class: "email-composer-send-btn",
				onclick: send,
			}),
			frappe.ui.dropdown({
				button: {
					icon: "chevron-down",
					variant: "solid",
					css_class: "email-composer-send-toggle",
					tooltip: __("More send options"),
				},
				align: "end",
				options: [
					{
						label: __("Schedule email"),
						icon: "calendar",
						onclick: () => {
							frappe.prompt(
								{
									label: __("Schedule Send At"),
									fieldname: "schedule_at",
									fieldtype: "Datetime",
									reqd: 1,
									default: fields.send_after.get_value(),
								},
								async (values) => {
									await this.dialog.set_value("send_after", values.schedule_at);
									send();
								},
								__("Schedule Send")
							);
						},
					},
				],
			})
		);
		$sendGroup.before(
			frappe.ui.button({
				label: __("Discard"),
				variant: "ghost",
				css_class: "email-composer-discard",
				onclick: () => {
					this.dialog.hide();
					this.clear_cache();
				},
			})
		);

		const $banner = this.$composer.find(".email-composer-banner");
		$banner.append(
			frappe.ui.button({
				icon: "x",
				variant: "ghost",
				size: "xs",
				tooltip: __("Dismiss"),
				css_class: "shrink-0",
				onclick: () => $banner.addClass("hidden"),
			})
		);
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
			const apply = () => {
				field.set_input(active ? 1 : 0);
				$item.toggleClass("active", active).attr("aria-checked", String(active));
			};
			apply();

			$item.on("click", (e) => {
				if ($item.hasClass("email-composer-menu-toggle")) e.stopPropagation();
				active = !active;
				apply();
				updateBanner();
			});
			$item.on("keydown", (e) => {
				if (e.key !== "Enter" && e.key !== " ") return;
				e.preventDefault();
				$item.trigger("click");
			});
		};

		let $printBtn = null;
		const syncPrintMenu = () =>
			$printBtn?.toggleClass("active", !!fields.attach_document_print.get_value());

		const renderPrintRow = (active) => {
			const $slot = this.$composer
				.find(".email-composer-print-format")
				.empty()
				.toggleClass("hidden", !active);
			if (!active) return;

			const $card = $(`
				<div class="flex items-center gap-2 p-3 rounded bg-surface-gray-1">
					${frappe.utils.icon("printer", "md", "", "", "shrink-0 text-ink-gray-6 pr-0.5", true)}
					<div class="flex flex-col gap-0.5 flex-1 min-w-0">
						<div class="email-composer-print-card__title text-base-medium text-ink-gray-8 truncate"></div>
						<div class="email-composer-print-card__meta text-base text-ink-gray-6 truncate"></div>
					</div>
					<div class="email-composer-print-card__actions flex items-center gap-1 shrink-0"></div>
				</div>
			`);
			$card.find(".email-composer-print-card__title").text(this.frm.docname);

			$card.find(".email-composer-print-card__actions").append(
				frappe.ui.button({
					icon: "eye",
					variant: "ghost",
					tooltip: __("Preview"),
					onclick: () => this.open_print_preview(),
				}),
				frappe.ui.button({
					icon: "pencil",
					variant: "ghost",
					tooltip: __("Change print settings"),
					onclick: () => this.open_print_settings(),
				}),
				frappe.ui.button({
					icon: "trash",
					variant: "ghost",
					tooltip: __("Remove"),
					onclick: () => {
						fields.attach_document_print.set_input(0);
						renderPrintRow(false);
						syncPrintMenu();
					},
				})
			);

			$slot.append($card);
			this.render_print_card_meta();
		};

		bindCheckIcon("send-me-a-copy", "send_me_a_copy");
		bindCheckIcon("send-read-receipt", "send_read_receipt");

		const $formatBtn = frappe.ui.button({
			icon: "type",
			variant: "ghost",
			tooltip: __("Formatting options"),
			attrs: { "data-action": "format" },
			onclick: () => {
				$formatBtn.toggleClass("active");
				this.setup_toolbar();
				this.$composer.find(".email-composer-toolbar-slot").toggleClass("hidden");
			},
		});

		if (this.frm) {
			const formats = frappe.meta.get_print_formats(this.frm.meta.name) || [];
			$printBtn = frappe.ui.dropdown({
				button: {
					icon: "printer",
					variant: "ghost",
					tooltip: __("Attach document print"),
				},
				options: () =>
					formats.map((format) => ({
						label: format,
						selected:
							!!fields.attach_document_print.get_value() &&
							fields.select_print_format.get_value() === format,
						onclick: async () => {
							await fields.select_print_format.set_value(format);
							fields.attach_document_print.set_input(1);
							renderPrintRow(true);
							syncPrintMenu();
						},
					})),
			});
			if (fields.attach_document_print.get_value()) {
				renderPrintRow(true);
			}
			syncPrintMenu();
		}
		this.sync_print_menu = () => syncPrintMenu();
		updateBanner();

		this.$composer.find(".email-composer-subject-row").append(this.make_template_dropdown());

		this.$composer.find(".email-composer-icon-row").prepend(
			frappe.ui.dropdown({
				button: { icon: "paperclip", variant: "ghost", tooltip: __("Attach files") },
				options: [
					{
						label: __("Select attachments"),
						icon: "paperclip",
						condition: () => this.get_available_attachments().length > 0,
						onclick: () => this.open_attachment_picker(),
					},
					{
						label: __("Add new attachments"),
						icon: "plus",
						onclick: () => this.upload_attachment(),
					},
				],
			}),
			$printBtn,
			$formatBtn
		);

		$original.hide();
	}

	setup_toolbar() {
		const $slot = this.$composer.find(".email-composer-toolbar-slot");
		if ($slot.children(".ql-toolbar").length) return; // already relocated + wired

		const $toolbar = this.$composer.find(
			'.frappe-control[data-fieldname="content"] .ql-toolbar'
		);
		if (!$toolbar.length) return; // Quill hasn't built the toolbar yet

		$slot.append($toolbar);

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
			$more.toggleClass("ql-active", expanded);
		});
	}

	make_template_dropdown() {
		return frappe.ui.dropdown({
			button: {
				label: __("Use template"),
				variant: "ghost",
				css_class: "email-composer-use-template",
			},
			align: "end",
			empty_text: __("No templates"),
			options: () =>
				this.get_email_template_names().then((names) =>
					names.map((name) => ({
						label: name,
						onclick: () => this.apply_email_template(name),
					}))
				),
		});
	}

	get_email_template_names() {
		if (!this.frm?.doctype) {
			return frappe.db
				.get_list("Email Template", { fields: ["name"], order_by: "name", limit: 0 })
				.then((rows) => (rows || []).map((row) => row.name));
		}

		return frappe
			.xcall("frappe.email.doctype.email_template.email_template.get_email_templates", {
				doctype: "Email Template",
				txt: "",
				searchfield: "name",
				start: 0,
				page_len: 0,
				filters: { reference_doctype: this.frm.doctype },
			})
			.then((rows) => (rows || []).map(([name]) => name));
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
				label: __("Use HTML editor"),
				fieldtype: "Switch",
				fieldname: "use_html",
				hidden: 1,
				onchange: (event) => this.on_use_html_toggle(event),
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
				depends_on: "attach_document_print",
			},
			{ fieldtype: "Column Break" },
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

	as_recipient_list(value) {
		if (Array.isArray(value)) return value;
		return String(value ?? "")
			.split(/[,;\n]/)
			.map((email) => email.trim())
			.filter(Boolean);
	}

	get_default_recipients(fieldname) {
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

	apply_email_template(template_name) {
		if (!template_name) return;
		frappe.call({
			method: "frappe.email.doctype.email_template.email_template.get_email_template",
			args: {
				template_name,
				doc: this.doc,
				sender: this.dialog.get_value("sender") || "",
			},
			callback: async (r) => {
				if (!r || !r.message) return;
				// An empty rich text editor still returns markup, don't carry it over.
				const is_blank =
					!this.dialog.get_value("use_html") &&
					this.dialog.fields_dict.content.quill?.getLength() <= 1;
				const existing = is_blank ? "" : this.get_email_content();
				if (r.message.use_html) {
					this.dialog.set_df_property("use_html", "hidden", 0);
					await this.dialog.set_value("use_html", 1);
				}
				this.set_email_content(r.message.message + existing);
				this.dialog.fields_dict.subject.set_value(r.message.subject);
				this.dialog.fields_dict.email_template.set_input(template_name);
			},
		});
	}

	prepare() {
		this.setup_multiselect_queries();
		this.setup_recipient_pills();
		this.setup_subject_and_recipients();
		this.setup_print();
		this.setup_attach();
		this.setup_email();
		this.setup_last_edited_communication();
		this.set_values();
	}

	setup_multiselect_queries() {
		["recipients", "cc", "bcc"].forEach((field) => {
			this.dialog.fields_dict[field].get_data = () => {
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
						// leave out addresses already in To, CC or BCC
						const added = new Set(
							["recipients", "cc", "bcc"].flatMap((name) =>
								(this.dialog.fields_dict[name].rows || []).map((row) =>
									row.toLowerCase()
								)
							)
						);
						control.set_data(
							(r.message || []).filter((d) => !added.has(d.value.toLowerCase()))
						);
					},
				});
			};
		});
	}

	setup_recipient_pills() {
		const me = this;
		this._recipient_avatars = this._recipient_avatars || {};

		["recipients", "cc", "bcc"].forEach((fieldname) => {
			const control = this.dialog.fields_dict[fieldname];
			if (!control) return;

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

			control.get_pill_html = function (value) {
				const $tag = frappe.ui.badge({
					label: this.get_label(value) || value,
					size: "lg",
					icon_right: "x",
					title: value,
					css_class: "email-composer-recipient-tag tb-selected-value",
					attrs: { "data-value": encodeURIComponent(value), draggable: "true" },
				});
				const photo = me._recipient_avatars?.[String(value).toLowerCase()] || null;
				$tag.prepend(
					frappe.ui.avatar.html({
						image: photo,
						label: value,
						size: "xs",
						css_class: "email-composer-tag-avatar",
					})
				);
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

			control.$multiselect_wrapper.on("mousedown", ".es-badge__affix", (e) => {
				e.preventDefault();
				this.remove_recipient(control, $(e.currentTarget).closest(".tb-selected-value"));
			});
			control.$multiselect_wrapper.on("keydown", ".es-badge__affix", (e) => {
				if (e.key !== "Enter" && e.key !== " ") return;
				e.preventDefault();
				this.remove_recipient(control, $(e.currentTarget).closest(".tb-selected-value"));
			});

			// drag a pill to move the address between To, CC and BCC
			control.$multiselect_wrapper.on("dragstart", ".tb-selected-value", (e) => {
				const value = decodeURIComponent(e.currentTarget.dataset.value || "");
				this.dragged_recipient = { control, value };
				e.originalEvent.dataTransfer.setData("text/plain", value);
				e.originalEvent.dataTransfer.effectAllowed = "move";
				// the drop re-renders the pills, taking this one out of the page, so a
				// delegated dragend never arrives and jQuery's remove() drops its own handlers
				e.currentTarget.addEventListener("dragend", () => this.end_recipient_drag(), {
					once: true,
				});
				// Chrome can cancel the drag if the layout changes inside dragstart
				setTimeout(() => this.show_cc_bcc_for_drag());
			});
			const $row = () => control.$wrapper.closest(".email-composer-row");
			control.$wrapper.on("dragover", (e) => {
				if (!this.dragged_recipient) return;
				e.preventDefault();
				$row().addClass("bg-surface-gray-1");
			});
			control.$wrapper.on("dragleave", (e) => {
				if (control.$wrapper[0].contains(e.originalEvent.relatedTarget)) return;
				$row().removeClass("bg-surface-gray-1");
			});
			control.$wrapper.on("drop", (e) => {
				if (!this.dragged_recipient) return;
				e.preventDefault();
				$row().removeClass("bg-surface-gray-1");
				this.move_recipient(this.dragged_recipient, control);
			});

			const clear_committed_text = () => {
				const typed = (control.$input?.val() || "").trim();
				if (typed && (control.rows || []).includes(typed)) {
					control.$input.val("");
				}
			};

			const render_pills = control.set_formatted_input.bind(control);
			control.set_formatted_input = function (value) {
				render_pills(value);
				clear_committed_text();
				me.fetch_recipient_avatars(control);
			};
			control.$input?.on("keydown", (e) => {
				if (e.key === "Enter") clear_committed_text();
			});

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

	fetch_recipient_avatars(control) {
		const cache = (this._recipient_avatars = this._recipient_avatars || {});
		const pending = (control.rows || [])
			.map((row) => String(row).toLowerCase())
			.filter((email) => email && !(email in cache));
		if (!pending.length) return;

		pending.forEach((email) => (cache[email] = null));

		frappe.call({
			method: "frappe.email.get_recipient_avatars",
			args: { emails: pending },
			callback: (r) => {
				const found = r.message || {};
				if (!Object.keys(found).length) return;
				Object.assign(cache, found);
				control.set_pill_html(control.rows || []);
			},
		});
	}

	show_cc_bcc_for_drag() {
		this.rows_shown_for_drag = ["cc", "bcc"].filter((type) => {
			const $row = this.$composer.find(`.email-composer-${type}-row`);
			if (!$row.hasClass("hidden")) return false;
			$row.removeClass("hidden");
			return true;
		});
	}

	end_recipient_drag() {
		this.dragged_recipient = null;
		this.$composer.find(".email-composer-row").removeClass("bg-surface-gray-1");
		for (const type of this.rows_shown_for_drag || []) {
			const filled = !!this.dialog.get_value(type)?.length;
			this.$composer.find(`.email-composer-${type}-row`).toggleClass("hidden", !filled);
			this.$composer
				.find(`.email-composer-toggle[data-target="${type}"]`)
				.attr("aria-pressed", String(filled));
		}
		this.rows_shown_for_drag = null;
	}

	move_recipient({ control: from, value }, to) {
		if (from === to) return;
		from.rows = (from.rows || []).filter((row) => row !== value);
		const exists = (to.rows || []).some((row) => row.toLowerCase() === value.toLowerCase());
		if (!exists) to.rows = [...(to.rows || []), value];

		for (const control of [from, to]) {
			control.set_pill_html(control.rows);
			control.parse_validate_and_set_in_model("");
		}
		this.remove_more_count(from.$multiselect_wrapper);
		this.collapse_recipient_row(from);
		this.expand_recipient_row(to);
	}

	remove_recipient(control, $tag) {
		const value = decodeURIComponent($tag.attr("data-value") || "");
		if (!value) return;
		control.rows = (control.rows || []).filter((row) => row !== value);
		control.set_pill_html(control.rows);
		control.parse_validate_and_set_in_model("");

		this.remove_more_count(control.$multiselect_wrapper);
		this.collapse_recipient_row(control);
	}

	expand_recipient_row(control) {
		const $wrapper = control.$multiselect_wrapper;
		if (!$wrapper?.length) return;
		clearTimeout(control._collapse_timer);
		$wrapper.removeClass("is-collapsed");
		this.remove_more_count($wrapper);
		$wrapper.find(".tb-selected-value").removeClass("hidden");
	}

	collapse_recipient_row(control) {
		const $wrapper = control.$multiselect_wrapper;
		if (!$wrapper?.length) return;
		if (control.$input?.is(":focus")) return;
		if ($wrapper[0].contains(document.activeElement)) return;
		if ($wrapper.is(":hover")) return;

		this.remove_more_count($wrapper);
		const $tags = $wrapper.find(".tb-selected-value").removeClass("hidden");
		if (!$tags.length) {
			$wrapper.removeClass("is-collapsed");
			return;
		}
		if ($wrapper.width() < 40) return;

		$wrapper.addClass("is-collapsed");
		const VISIBLE = 2;
		if ($tags.length <= VISIBLE) return;

		const hidden = $tags
			.slice(VISIBLE)
			.addClass("hidden")
			.map((_, tag) => decodeURIComponent(tag.dataset.value))
			.get();
		const $more = frappe.ui.badge({
			label: __("+{0} more", [hidden.length]),
			size: "lg",
			variant: "ghost",
			css_class: "email-composer-more-count",
		});
		frappe.ui.hover_card($more, {
			align: "start",
			content: () => {
				const $list = $(
					`<div class="flex flex-col gap-2 max-w-xs max-h-80 overflow-y-auto text-sm text-ink-gray-7"></div>`
				);
				hidden.forEach((email) => {
					$(`<div class="flex items-center gap-2 min-w-0"></div>`)
						.append(
							frappe.ui.avatar.html({
								image: this._recipient_avatars?.[email.toLowerCase()] || null,
								label: email,
								size: "xs",
								css_class: "shrink-0",
							}),
							$(`<span class="truncate"></span>`).text(email)
						)
						.appendTo($list);
				});
				return $list[0];
			},
		});
		$wrapper.append($more);
	}

	remove_more_count($wrapper) {
		const $more = $wrapper.find(".email-composer-more-count");
		// close its hover card first, or an open card stays on screen after the badge is gone
		$more.data("es-hover-card")?.destroy();
		$more.remove();
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
			fields.recipients.set_value(this.as_recipient_list(this.last_email.recipients));
			if (this.reply_all) {
				fields.cc.set_value(this.as_recipient_list(this.last_email.cc));
				fields.bcc.set_value(this.as_recipient_list(this.last_email.bcc));
			}
		} else {
			fields.recipients.set_value(this.as_recipient_list(this.last_email.sender));
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
				fields.cc.set_value(this.as_recipient_list(this.cc));
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
		for (const fieldname of ["recipients", "cc", "bcc"]) {
			await this.dialog.set_value(fieldname, this.as_recipient_list(this[fieldname]));
		}
		await this.dialog.set_value("sender", this.sender || "");

		const subject = this.subject ? frappe.utils.html2text(this.subject) : "";
		await this.dialog.set_value("subject", subject);

		await this.set_values_from_last_edited_communication();
		await this.set_content();

		// set default email template for the first email in a document
		if (this.frm && !this.is_a_reply && !this.content_set) {
			const email_template = this.frm.meta.default_email_template || "";
			await this.dialog.set_value("email_template", email_template);
		}

		if (this.dialog.get_value("use_html")) {
			this.dialog.set_df_property("use_html", "hidden", 0);
		}

		if (this.$composer) {
			for (const type of ["cc", "bcc"]) {
				if (this.dialog.get_value(type)?.length) {
					this.$composer.find(`.email-composer-${type}-row`).removeClass("hidden");
					this.$composer
						.find(`.email-composer-toggle[data-target="${type}"]`)
						.attr("aria-pressed", "true");
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

	open_print_preview() {
		if (!this.frm) return;

		const fields = this.dialog.fields_dict;
		const params = {
			doctype: this.frm.doctype,
			name: this.frm.docname,
			format: fields.select_print_format?.get_value() || "Standard",
			_lang: fields.print_language?.get_value() || frappe.boot.lang,
		};

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
					this.render_print_card_meta();
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

		attach.empty().append(`<div class="attach-list flex flex-wrap gap-1"></div>`);
		this.upload_attachment = () => new frappe.ui.FileUploader(args);
		this.render_attachment_rows();
	}

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

	render_attachment_rows(attachment) {
		const attachment_rows = $(this.dialog.fields_dict.select_attachments.wrapper).find(
			".attach-list"
		);
		this.selected_attachments = this.selected_attachments || new Set();

		if (attachment?.name) this.selected_attachments.add(attachment.name);

		attachment_rows.empty();
		this.get_available_attachments().forEach((f) => {
			if (!this.selected_attachments.has(f.name)) return;
			f.file_url = frappe.urllib.get_full_url(f.file_url);
			attachment_rows.append(this.get_attachment_row(f));
		});
	}

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
			<label class="email-composer-file-row flex items-center gap-3 mb-0 px-2 py-1.5 rounded-md cursor-pointer">
				<input type="checkbox" class="shrink-0 cursor-pointer">
				<span class="email-composer-file-row__thumb flex items-center justify-center shrink-0 size-8 bg-surface-gray-3 text-ink-gray-7 text-xs-medium" data-ext="${frappe.utils.escape_html(
					extension
				)}"></span>
				<span class="flex flex-col gap-1 flex-1 min-w-0">
					<span class="email-composer-file-row__name text-sm text-ink-gray-8 truncate"></span>
					<span class="email-composer-file-row__meta text-xs text-ink-gray-5 truncate"></span>
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
			$thumb.addClass("is-image").css("background-image", `url("${CSS.escape(source)}")`);
		} else {
			$thumb.text(extension.slice(0, 4));
			if (extension === "PDF") $thumb.addClass("is-pdf");
		}
		return $row;
	}

	open_attachment_picker() {
		const available = this.get_available_attachments();
		this.selected_attachments = this.selected_attachments || new Set();

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

		const $list = $(
			`<div class="email-composer-file-picker flex flex-col gap-0.5 max-h-80 overflow-y-auto"></div>`
		);
		available.forEach((f) => $list.append(this.get_file_picker_row(f)));
		this.attachment_picker.fields_dict.files.$wrapper.empty().append($list);
		this.attachment_picker.show();
	}

	get_attachment_row(attachment) {
		const $row = $(`<div class="email-composer-attach-pill">
			<input type="checkbox" checked hidden>
		</div>`);
		$row.find("input").attr("data-file-name", attachment.name);

		const size = attachment.file_size
			? frappe.form.formatters.FileSize(attachment.file_size)
			: null;
		const $badge = frappe.ui.badge({
			label: size ? `${attachment.file_name} (${size})` : attachment.file_name,
			icon: "paperclip",
			icon_right: "x",
			size: "lg",
			title: attachment.file_name,
			css_class: "max-w-xs",
		});
		$badge
			.contents()
			.filter((_, node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim())
			.wrap('<span class="pill-label ellipsis"></span>');

		const remove = () => {
			this.selected_attachments?.delete(attachment.name);
			$row.remove();
		};
		$badge
			.find(".es-badge__affix")
			.attr({ role: "button", tabindex: 0, "aria-label": __("Remove") })
			.on("click", remove)
			.on("keydown", (e) => {
				if (e.key !== "Enter" && e.key !== " ") return;
				e.preventDefault();
				remove();
			});
		return $row.append($badge);
	}

	setup_email() {
		// email
		const fields = this.dialog.fields_dict;

		if (this.attach_document_print) {
			$(fields.attach_document_print.input).click();
		}
	}

	send_action() {
		const me = this;
		const btn = me.dialog.get_primary_btn();
		const form_values = this.get_values();
		if (!form_values) return;

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
			for (const suffix of ["", "_use_html"]) {
				localforage.removeItem(this.frm.doctype + this.frm.docname + suffix).catch((e) => {
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

	get_content_field() {
		if (this.dialog.fields_dict.use_html.value) {
			return this.dialog.fields_dict.html_content;
		} else {
			return this.dialog.fields_dict.content;
		}
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
