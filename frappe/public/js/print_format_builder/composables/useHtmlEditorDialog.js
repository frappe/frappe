import { render_jinja_html, strip_unsafe_html } from "../utils";

const PREVIEW_CSS = `
	* { box-sizing: border-box; }
	body { margin: 0; padding: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; color: #333; line-height: 1.5; }
	img { max-width: 100%; height: auto; display: block; }
	table { border-collapse: collapse; width: 100%; }
	td, th { vertical-align: top; }
`;

function write_preview(iframe, html) {
	const doc = iframe?.contentDocument;
	if (!doc) return;
	doc.open();
	doc.write(
		`<!DOCTYPE html><html><head><meta charset="utf-8"><style>${PREVIEW_CSS}</style></head><body>${strip_unsafe_html(
			html
		)}</body></html>`
	);
	doc.close();
}

export function open_html_editor({ title, initial_html, on_save, doctype, docname }) {
	const d = new frappe.ui.Dialog({
		title,
		size: "extra-large",
		fields: [
			{
				fieldname: "split_layout",
				fieldtype: "HTML",
				options: `<div class="pfb-html-split">
					<div class="pfb-html-split-pane">
						<div class="pfb-html-split-label">${__("HTML")}</div>
						<div class="pfb-html-ctrl-host"></div>
					</div>
					<div class="pfb-html-split-divider"></div>
					<div class="pfb-html-split-pane">
						<div class="pfb-html-split-label">${__("Preview")}</div>
						<iframe class="pfb-html-preview-frame"></iframe>
					</div>
				</div>`,
			},
		],
		primary_action_label: __("Save"),
		primary_action: () => {
			on_save(strip_unsafe_html(d._html_ctrl?.get_value?.() ?? ""));
			d.hide();
		},
		on_page_show: mount,
	});
	d.show();

	function mount() {
		const host = d.$wrapper.find(".pfb-html-ctrl-host")[0];
		const preview = d.$wrapper.find(".pfb-html-preview-frame")[0];
		if (!host) return;

		const ctrl = frappe.ui.form.make_control({
			parent: host,
			df: { fieldtype: "Code", fieldname: "html_code", options: "HTML", show_label: false },
			render_input: true,
		});
		ctrl.set_value(initial_html || "");
		d._html_ctrl = ctrl;

		const update_preview = async (html) => {
			write_preview(
				preview,
				(await render_jinja_html(html || "", doctype, docname)) ?? html ?? ""
			);
		};
		update_preview(initial_html);

		ctrl.load_lib().then(() => {
			ctrl.editor.on(
				"change",
				frappe.utils.debounce(() => update_preview(ctrl.editor.getValue()), 300)
			);
			ctrl.editor.resize();
		});
	}
}
