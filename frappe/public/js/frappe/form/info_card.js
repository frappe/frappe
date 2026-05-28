export class InfoCard {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
		this.setup_click();
	}
	make() {
		this.make_toggle_button();
		this.make_card();
	}
	make_toggle_button() {
		$(
			`${frappe.utils.icon(
				"info",
				"xs",
				"",
				"",
				"cursor-pointer m-0 info-trigger card-icons"
			)}`
		).appendTo($(this.label_span));
		$(this.label_span).find("svg").attr("role", "button");
		$(this.label_area).css({
			display: "flex",
			gap: "6px",
			"align-items": "center",
			"white-space": "nowrap",
		});
	}
	make_card() {
		const me = this;
		this.$info_card = $("<div class='info-card'></div>").appendTo(this.label_span);
		let card_args = {
			title: "",
			message: this.df.show_description_on_click ? this.df.description || "" : "",
			parent: this.$info_card,
			trigger: $(this.label_span).find("svg").get(0),
			close_button: true,
			popper: true,
			hide_icon: true,
			custom_class: "py-1 px-1",
		};
		if (this.df.documentation_url) {
			if (this.df.description && this.df.show_description_on_click) {
				card_args.message += "<br>";
			}
			card_args.message += `<a style="display: inline-block; text-underline-offset: 2px;" class="py-1" href="${
				this.df.documentation_url
			}" target="_blank">${__("View Documentation")}</a>`;
		}
		this.card = new frappe.ui.SidebarCard(card_args);
	}
	setup_click() {
		const me = this;
		$(this.label_span)
			.find(".info-trigger")
			.on("click", (event) => {
				event.preventDefault();
				me.card.toggle();
			});
		$(document).on("click", function (e) {
			const path = e.originalEvent?.composedPath();
			if (!path || !path.includes(me.label_area)) {
				me.card.hide();
			}
		});
	}
}
