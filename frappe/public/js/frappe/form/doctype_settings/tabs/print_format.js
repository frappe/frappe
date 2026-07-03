frappe.doctype_settings.register("print-format", function (panel, doctype) {
	// Captured each load: current default + a printable sample doc for previews.
	let default_pf = null;
	let sample_name = null;

	// Editing a format opens it in the Print Format Builder.
	const open_edit = (name) => {
		panel.dialog.hide();
		frappe.set_route("print-format-builder", name);
	};
	// Mirror the Print Format Builder's own "create" flow: make a builder-beta format for
	// this doctype (autoname is Prompt, so ask for the name), then open it in the builder.
	const create = () => {
		frappe.prompt(
			{
				label: __("New Print Format Name"),
				fieldname: "print_format_name",
				fieldtype: "Data",
				reqd: 1,
			},
			({ print_format_name }) => {
				frappe.db
					.insert({
						doctype: "Print Format",
						name: print_format_name,
						doc_type: doctype,
						print_format_builder_beta: 1,
					})
					.then((doc) => {
						panel.dialog.hide();
						frappe.set_route("print-format-builder", doc.name);
					});
			},
			__("New Print Format"),
			__("Create")
		);
	};
	panel.set_view({
		title: __("Print Format"),
		description: __(
			"Configure print formats for {0}. You can choose a format when printing or emailing a document.",
			[doctype]
		),
		actions: [{ label: __("New"), icon: "plus", click: create }],
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
		])
			.then(([formats, sample, current_default]) => {
				sample_name = sample && sample.length ? sample[0].name : null;
				default_pf = current_default;
				render(formats || []);
			})
			.catch(() => frappe.doctype_settings.render_error(panel, load));
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
				icon: frappe.doctype_settings.tab_icon("print-format"),
				title: __("No Print Formats found"),
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

		const $card = $(`
			<div class="dts-pf-card">
				<div class="dts-pf-preview">
					<span class="es-badge dts-pf-badge hide" data-theme="blue">${__("Custom")}</span>
					<button type="button" class="dts-pf-star" data-selected="${
						is_default ? "true" : "false"
					}">${frappe.utils.icon("star", "sm")}</button>
					<div class="dts-pf-thumb">
						<span class="dts-pf-placeholder">${frappe.utils.icon("printer", "lg")}</span>
					</div>
				</div>
				<div class="dts-pf-footer">
					<span class="dts-pf-name ellipsis"></span>
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

		$card
			.find(".dts-pf-name")
			.text(f.name)
			.on("click", () => open_edit(f.name));

		return $card;
	}

	function preview(pf) {
		if (!sample_name) {
			frappe.msgprint({
				title: __("No document to preview"),
				message: __("Create a {0} document first to preview this print format.", [
					doctype,
				]),
				indicator: "orange",
			});
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Preview: {0}", [frappe.utils.escape_html(pf)]),
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "preview" }],
		});
		const $wrapper = dialog.fields_dict.preview.$wrapper;
		$wrapper.html(`<div class="text-muted small">${__("Loading")}</div>`);
		dialog.show();

		// Render the print HTML server-side and inject it as a static (JS-free) iframe via
		// srcdoc. Loading the live /printview page in an iframe boots a full Frappe app
		// whose router throws a cross-realm error if the dialog closes mid-load. We mirror
		// the print page's own structure: the base print stylesheet (absolute URL, since
		// srcdoc has no base) + the format style, with the html in a `.print-format` wrapper.
		frappe.call({
			method: "frappe.www.printview.get_html_and_style",
			args: {
				doc: doctype,
				name: sample_name,
				print_format: pf,
				no_letterhead: 0,
				trigger_print: 0,
			},
			callback: (r) => {
				if (r.exc || !r.message) return;
				const base_url = frappe.urllib.get_base_url();
				const print_css = frappe.assets.bundled_asset("print.bundle.css");
				// A format's CSS is user/admin-authored and untrusted. Escaping every "</" stops
				// a "</style>" (or any other closing tag) inside it from breaking out of the
				// <style> block and injecting raw HTML into the srcdoc.
				const safe_style = (r.message.style || "").replace(/<\//g, "<\\/");
				// Sandboxed with no `allow-same-origin` (and no `allow-scripts`): the iframe gets
				// an opaque origin, so it can't run scripts, read/send this site's cookies, or
				// access same-origin storage — even if the CSS/HTML above were bypassed some
				// other way. Loading the linked stylesheet doesn't require allow-same-origin.
				const $iframe = $(
					'<iframe class="dts-preview-frame" frameborder="0" sandbox=""></iframe>'
				);
				$wrapper.empty().append($iframe);
				$iframe[0].srcdoc = `<!DOCTYPE html>
<html>
	<head>
		<link href="${base_url}${print_css}" rel="stylesheet">
		<style>${safe_style}</style>
	</head>
	<body>
		<div class="print-format print-format-preview">${r.message.html || ""}</div>
	</body>
</html>`;
			},
		});
	}

	function set_default(print_format) {
		return frappe.doctype_settings.set_property(doctype, "default_print_format", print_format);
	}
});
