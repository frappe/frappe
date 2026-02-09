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
				"message-circle-question-mark",
				"sm",
				"",
				"",
				"cursor-pointer m-0"
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
			message: this.df.description,
			parent: this.$info_card,
			trigger: $(this.label_span).find("svg").get(0),
			close_button: true,
			popper: true,
		};
		if (this.df.documentation_url) {
			card_args.primary_action_label = "Read More";
			card_args.primary_action_suffix_icon = "square-arrow-out-up-right";
			card_args.primary_action = function () {
				window.open(me.df.documentation_url);
			};
			card_args.styles = {
				"sidebar-card-button-bg-color": "var(--surface-gray-2)",
				"sidebar-card-button-color": "var(--ink-gray-7)",
				"sidebar-card-button-outline": "var(--ink-gray-7)",
			};
		}
		this.card = new frappe.ui.SidebarCard(card_args);
	}
	setup_click() {
		const me = this;
		$(this.label_span)
			.find("svg")
			.on("click", (event) => {
				event.preventDefault();
				me.card.toggle();
			});
		$(document).on("click", function (e) {
			if (!e.originalEvent.composedPath().includes(me.label_area)) {
				me.card.hide();
			}
		});
	}
}
