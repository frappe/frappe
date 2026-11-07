import Widget from "./base_widget.js";

frappe.provide("frappe.utils");

export default class LinksWidget extends Widget {
	constructor(opts) {
		opts.icon = opts.icon || "file";
		super(opts);
	}

	get_config() {
		return {
			name: this.name,
			links: JSON.stringify(this.links),
			link_count: this.links.length,
			label: this.label,
			hidden: this.hidden,
			description: this.description,
		};
	}

	set_body() {
		if (!this.options) {
			this.options = {};
			this.options.links = this.links;
		}
		this.widget.addClass("links-widget-box");

		if (this.description) {
			const description = $(`
				<button class="btn-reset card-description-btn ml-2">
					${frappe.utils.icon("circle-question-mark", "sm")}
				</button>
			`).appendTo(this.widget.find(".widget-title"));

			frappe.ui.hover_card(description, {
				side: "top",
				open_delay: 0,
				close_delay: 0,
				content: () => __(this.description),
			});
		}

		const is_link_disabled = (item) => {
			return item.dependencies && item.incomplete_dependencies;
		};
		const disabled_dependent = (item) => {
			return is_link_disabled(item) ? "disabled-link" : "";
		};

		const get_indicator_color = (item) => {
			if (item.open_count) {
				return "red";
			}
			if (item.onboard) {
				return item.count ? "blue" : "amber";
			}
			return "gray";
		};

		const get_link_for_item = (item) => {
			if (is_link_disabled(item)) {
				return `<span class="link-content ellipsis disabled-link">${item.link_title}</span>`;
			}

			if (item.youtube_id)
				return `
					<span class="link-content help-video-link ellipsis" data-youtubeid="${item.youtube_id}">
						${item.link_title}
					</span>
				`;

			return `
				<span class="link-content">
					<span class="link-text">${item.link_title}</span>
				</span>
			`;
		};

		this.link_list = this.links.map((item) => {
			const opts = {
				name: item.link_to,
				type: item.link_type,
				doctype: item.doctype,
				is_query_report: item.is_query_report,
				report_ref_doctype: item.report_ref_doctype,
			};

			if (item.link_type.toLowerCase() == "report" && !item.is_query_report) {
				opts.doctype = item.dependencies;
			}

			const route = frappe.utils.generate_route(opts);
			item.link_title = item.label ? item.label : item.name;

			const $link = $(`
				<a href="${route}" class="link-item
					${item.onboard ? "onboard-spotlight" : ""} ${disabled_dependent(item)}"
					type="${item.type}" title="${item.link_title}"
				>
					${get_link_for_item(item)}
				</a>
			`);

			if (item.description) {
				frappe.ui.hover_card($link.find(".link-text"), {
					side: "top",
					open_delay: 600,
					close_delay: 100,
					content: () =>
						$(`<div class="es-popover__header"></div>`).append(
							$(`<div class="es-popover__title"></div>`).text(item.link_title),
							$(`<p class="es-popover__description"></p>`).text(__(item.description))
						)[0],
				});
			}

			if (is_link_disabled(item)) {
				frappe.ui.hover_card($link.find(".link-content"), {
					side: "top",
					open_delay: 0,
					close_delay: 0,
					content: () =>
						!this.in_customize_mode &&
						$(`<div></div>`).append(
							$(`<div class="small text-muted"></div>`).text(
								__("You need to create these first:")
							),
							$(`<div class="small"></div>`).text(
								item.incomplete_dependencies.join(", ")
							)
						)[0],
				});
			}

			return $link;
		});
		if (this.in_customize_mode) {
			this.body.empty();
		}
		this.link_list.forEach((link) => link.appendTo(this.body));
	}

	setup_events() {
		this.link_list.forEach((link) => {
			const link_label = link.find(".link-content");

			if (!link.hasClass("disabled-link")) {
				link_label.click((event) => {
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
