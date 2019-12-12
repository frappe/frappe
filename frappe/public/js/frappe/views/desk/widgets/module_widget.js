import { generate_route } from "./utils";
import LinkWidget from "./link_widget.js";

export default class ModuleWidget extends LinkWidget {
	constructor(opts) {
		super(opts);
	}

	make_widget() {
		super.make_widget();
		this.make_dropdown();
	}

	make_dropdown() {
		this.dropdown && this.dropdown.remove();

		this.dropdown = this.get_dropdown_body();

		let wrapper = this.widget.find(".module-box-content-wrapper");
		this.dropdown.appendTo(wrapper);

		this.dropdown_button = this.dropdown.find(".octicon-chevron-down");
		this.dropdown_body = this.dropdown.find(".dropdown-body");
		this.customize_dropdown = this.dropdown.find(".customize-module");
	}

	get_dropdown_body() {
		const list_html = this.data.links.map(item => {
			return `<li class="${item.class || null}">
					<a class="list-item" href="${generate_route(item)}">${item.label}</a>
				</li>`;
		});

		return $(`<div class="inline-block relative">
					<div>
						<span class="pull-right">
							<i class="octicon octicon-chevron-down text-muted"></i>
						</span>
					</div>
					<div class="absolute mt-default z-20 pin-r dropdown-body" style="display: none;">
						<ul class="list-reset border">
							${list_html.join(" ")}
							<li class="border-top customize-module"><div class="list-item">Customize</div></li>
						</ul>
					</div>
				</div>`);
	}

	setup_events() {
		this.setup_dropdown_events();
		this.setup_customize_button();
	}

	setup_dropdown_events() {
		this.dropdown_button.on("click", event => {
			this.dropdown_body.toggle();
			event.stopPropagation();
		});

		$(window).click(() => {
			this.dropdown_body.hide();
		});
	}

	setup_customize_button() {
		this.customize_dropdown.on("click", () => {
			const module_links = this.data.links;
			const d = new frappe.ui.Dialog({
				title: __("Customize Shortcuts"),
				fields: [
					{
						label: __("Shortcuts"),
						fieldname: "links",
						fieldtype: "MultiSelectPills",
						get_data: () => {
							return frappe
								.xcall(
									"frappe.desk.moduleview.get_links_for_module",
									{
										app: this.data.app,
										module: this.data.module_name
									}
								)
								.then(links => {
									return links;
								});
						},
						default: this.data.links
							.filter(l => !l.hidden)
							.map(l => l.name)
					}
				],
				primary_action_label: __("Save"),
				primary_action: ({ links }) => {
					frappe
						.call(
							"frappe.desk.moduleview.update_links_for_module",
							{
								app: this.data.app,
								module_name: this.data.module_name,
								links: links || []
							}
						)
						.then(r => {
							this.data.links = r.message;
							this.make_dropdown();
							this.setup_events();
						});
					d.hide();
				}
			});

			d.show();
		});
	}
}
