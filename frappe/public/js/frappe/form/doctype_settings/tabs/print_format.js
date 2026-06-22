frappe.doctype_settings.register("print-format", function (panel, doctype) {
	// Captured each load: current default + a printable sample doc for previews.
	let default_pf = null;
	let sample_name = null;

	const open_edit = (name) => {
		panel.dialog.hide();
		frappe.set_route("Form", "Print Format", name);
	};
	const create = () => {
		panel.dialog.hide();
		frappe.new_doc("Print Format", { doc_type: doctype });
	};
	const printview_url = (pf) =>
		`/printview?${$.param({
			doctype,
			name: sample_name,
			format: pf,
			no_letterhead: 0,
			trigger_print: 0,
		})}`;

	panel.set_view({
		title: __("Print Format"),
		description: __("Print formats available for {0}.", [doctype]),
		actions: [{ label: __("New"), icon: "add", primary: true, click: create }],
		render: () => load(),
	});

	function load() {
		panel.body.empty();
		$(`<div class="text-muted small">${__("Loading")}</div>`).appendTo(panel.body);

		// Reuse generic client APIs: get_list for the formats and a printable sample
		// (submitted-only for submittable doctypes) for previews. The current default is
		// read fresh from the server each load — the cached client meta isn't refreshed
		// after set_default, so relying on it would leave the star on the old format.
		const meta = frappe.get_meta(doctype) || {};
		const sample_filters = meta.is_submittable ? { docstatus: 1 } : {};

		Promise.all([
			frappe.db.get_list("Print Format", {
				filters: { doc_type: doctype },
				fields: ["name", "standard", "preview_image"],
				order_by: "standard asc, name asc",
				limit: 0,
			}),
			frappe.db.get_list(doctype, {
				filters: sample_filters,
				fields: ["name"],
				order_by: "modified desc",
				limit: 1,
			}),
			get_default(),
		]).then(([formats, sample, current_default]) => {
			sample_name = sample && sample.length ? sample[0].name : null;
			default_pf = current_default;
			render(formats || []);
		});
	}

	// Default print format lives in a Property Setter for standard doctypes (Customize
	// Form path) or on the DocType row for custom ones; the Property Setter wins.
	function get_default() {
		return Promise.all([
			frappe.db.get_value(
				"Property Setter",
				{ doc_type: doctype, property: "default_print_format" },
				"value"
			),
			frappe.db.get_value("DocType", doctype, "default_print_format"),
		]).then(([ps, dt]) => {
			const ps_val = ps && ps.message ? ps.message.value : null;
			const dt_val = dt && dt.message ? dt.message.default_print_format : null;
			return ps_val || dt_val || null;
		});
	}

	function render(formats) {
		panel.body.empty();

		if (!formats.length) {
			frappe.doctype_settings.empty_state(panel.body, {
				title: __("No print formats yet"),
				description: __("Create a print format to customize how {0} prints.", [doctype]),
				action: { label: __("New Print Format"), onclick: create },
			});
			return;
		}

		const $grid = $('<div class="dts-pf-grid"></div>').appendTo(panel.body);
		formats.forEach((f) => $grid.append(make_card(f)));
	}

	function make_card(f) {
		const is_default = f.name === default_pf;
		const is_custom = f.standard !== "Yes";

		const star_icon = is_default ? "es-solid-star" : "es-line-star";
		const $card = $(`
			<div class="dts-pf-card">
				<div class="dts-pf-preview">
					<span class="es-badge dts-pf-badge hide" data-theme="blue">${__("Custom")}</span>
					<button type="button" class="dts-pf-star">${frappe.utils.icon(star_icon, "sm")}</button>
					<div class="dts-pf-thumb">
						<span class="dts-pf-placeholder">${frappe.utils.icon("printer", "lg")}</span>
					</div>
				</div>
				<div class="dts-pf-footer">
					<span class="dts-pf-name"></span>
				</div>
			</div>
		`);

		const $thumb = $card.find(".dts-pf-thumb");
		const $star = $card.find(".dts-pf-star");

		if (is_custom) $card.find(".dts-pf-badge").removeClass("hide");

		// Thumbnail comes from the Print Format's own `preview_image` (generated from its
		// form's "Generate Preview" button); formats without one show the placeholder.
		if (f.preview_image) {
			$thumb
				.find(".dts-pf-placeholder")
				.replaceWith($('<img class="dts-pf-img" />').attr("src", f.preview_image));
		}

		// The page thumbnail → full preview.
		$thumb.on("click", () => preview(f.name));

		// The star is the set-default control: gold + persistent when default; otherwise
		// it appears on hover and sets this format as default on click.
		if (is_default) {
			$card.addClass("is-default");
			$star.attr("title", __("Default")).on("click", (e) => e.stopPropagation());
		} else {
			$star.attr("title", __("Set as default")).on("click", (e) => {
				e.stopPropagation();
				set_default(f.name).then(() => load());
			});
		}

		$card.find(".dts-pf-name").text(f.name).on("click", () => open_edit(f.name));

		return $card;
	}

	function preview(pf) {
		if (!sample_name) {
			frappe.msgprint({
				title: __("No document to preview"),
				message: __("Create a {0} document first to preview this print format.", [doctype]),
				indicator: "orange",
			});
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Preview: {0}", [frappe.utils.escape_html(pf)]),
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "preview" }],
		});
		dialog.fields_dict.preview.$wrapper.html(
			`<iframe class="dts-preview-frame" frameborder="0" src="${printview_url(pf)}"></iframe>`
		);
		dialog.show();
	}

	// Sets the doctype's default print format by writing a Property Setter — the same
	// override Customize Form / make_default create for non-custom doctypes (which is all
	// DocType Settings exposes). Property Setter's validation dedupes the previous one.
	function set_default(print_format) {
		return frappe.db
			.insert({
				doctype: "Property Setter",
				doctype_or_field: "DocType",
				doc_type: doctype,
				property: "default_print_format",
				property_type: "Data",
				value: print_format,
			})
			.then(() => frappe.show_alert({ message: __("Default updated"), indicator: "green" }));
	}
});
