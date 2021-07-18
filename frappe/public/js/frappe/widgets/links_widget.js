import Widget from "./base_widget.js";

frappe.provide("frappe.utils");

export default class LinksWidget extends Widget {
	constructor(opts) {
		opts.icon = opts.icon || 'file';
		super(opts);
	}

	get_config() {
		return {
			name: this.name,
			links: JSON.stringify(this.links),
			label: this.label,
			hidden: this.hidden,
		};
	}

	set_body() {
		this.options = {};
		this.options.links = this.links;
		this.widget.addClass("links-widget-box");
		const is_link_disabled = item => {
			return item.dependencies && item.incomplete_dependencies;
		};
		const disabled_dependent = item => {
			return is_link_disabled(item) ? "disabled-link" : "";
		};

		const get_indicator_color = item => {
			if (item.open_count) {
				return "red";
			}
			if (item.onboard) {
				return item.count ? "blue" : "yellow";
			}
			return "gray";
		};

		const get_link_for_item = item => {
			if (is_link_disabled(item)) {
				return `<span class="link-content ellipsis disabled-link">${
					item.label ? item.label : item.name
				}</span>
					<div class="module-link-popover popover fade top in" role="tooltip" style="display: none;">
						<div class="arrow"></div>
						<h3 class="popover-title" style="display: none;"></h3>
						<div class="popover-content" style="padding: 12px;">
							<div class="small text-muted">${__("You need to create these first: ")}</div>
							<div class="small">${item.incomplete_dependencies.join(", ")}</div>
						</div>
					</div>`;
			}

			if (item.youtube_id)
				return `<span class="link-content help-video-link ellipsis" data-youtubeid="${item.youtube_id}">
						${item.label ? item.label : item.name}</span>`;

			return `<span class="link-content ellipsis">${item.label ? item.label : item.name}</span>`;
		};

		this.link_list = this.links.map(item => {
			const opts = {
				name: item.link_to,
				type: item.link_type,
				doctype: item.doctype,
				is_query_report: item.is_query_report
			};

			if (item.link_type.toLowerCase() == "report" && !item.is_query_report) {
				opts.doctype = item.dependencies;
			}

			const route = frappe.utils.generate_route(opts);

			return $(`<a href="${route}" class="link-item ellipsis ${
				item.onboard ? "onboard-spotlight" : ""
			} ${disabled_dependent(item)}" type="${item.type}">
					<span class="indicator-pill no-margin ${get_indicator_color(item)}"></span>
					${get_link_for_item(item)}
			</a>`);
		});

		this.link_list.forEach(link => link.appendTo(this.body));
	}

	setup_events() {
		this.link_list.forEach(link => {
			// Bind Popver Event
			const link_label = link.find(".link-content");

			if (link.hasClass("disabled-link")) {
				const popover = link.find(".module-link-popover");

				link_label.mouseover(() => {
					if (this.in_customize_mode) return;
					popover.show();
				});
				link_label.mouseout(() => popover.hide());
			} else {
				link_label.click(event => {
					if (this.in_customize_mode) return;

					if (link_label.hasClass("help-video-link")) {
						let yt_id = event.currentTarget.dataset.youtubeid;
						frappe.help.show_video(yt_id);
					}
				});
			}
		});
	}
}
