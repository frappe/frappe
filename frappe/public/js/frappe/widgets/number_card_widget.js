import Widget from "./base_widget.js";
import { go_to_list_with_filters } from "./utils";

export default class NumberCardWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	get_config() {
		return {
			name: this.name,
			label: this.label,
			color: this.color,
			hidden: this.hidden,
		};
	}

	refresh() {
		this.set_body();
	}

    set_body() {
		this.widget.addClass("number-widget-box");
		$(this.body).html(`<div class="number-card-loading text-muted">
			${__('Loading...')}
		</div>`);
		this.make_card();
	}

	make_card() {
		frappe.model.with_doc("Number Card", this.name).then(card => {
			if (!card) {
				if (this.document_type) {
					this.set_doc_args();
					frappe.xcall(
						'frappe.desk.doctype.number_card.number_card.create_number_card',
						{'args': this.card_doc}
					).then(doc => {
						this.name = doc.name;
						this.widget.attr('data-widget-name', this.name);
						this.render_card();
					});
				} else {
					// widget doesn't exist so delete
					this.delete(false);
					return;
				}
			} else {
				this.card_doc = card;
				this.render_card();
			}
			this.set_events();
		});
	}

	set_events() {
		$(this.body).click(() => {
			if (this.in_customize_mode) return;
			let filters = JSON.parse(this.card_doc.filters_json);
			go_to_list_with_filters(this.card_doc.document_type, filters);
		});
	}

	set_doc_args() {
		this.card_doc = Object.assign({}, {
			document_type: this.document_type,
			label: this.label,
			function: this.function,
			aggregate_function_based_on: this.aggregate_function_based_on,
			color: this.color,
			filters_json: this.stats_filter
		});
	}

	render_card() {
		this.prepare_actions();
		this.get_number().then(() => {
			$(this.body).html(`<div class="widget-content">
				<div class="number" style="color:${this.card_doc.color}">${this.number_html}</div>
				<div class="number-text">${this.card_doc.label}</div>
				</div>`);
		});
	}

	get_number() {
		return frappe.xcall('frappe.desk.doctype.number_card.number_card.get_result', {doc: this.card_doc}).then(res => {
			const number_order = res.toFixed().length - 1;
			if (number_order > 12) {
				this.number_html = `&asymp; 10<sup>${number_order}</sup>`;
			} else {
				this.number_html = res;
			}
		});
	}

	prepare_actions() {
		let actions = [
			{
				label: __("Refresh"),
				action: "action-refresh",
				handler: () => {
					this.render_card();
				}
			},
			{
				label: __("Edit"),
				action: "action-edit",
				handler: () => {
					frappe.set_route(
						"Form",
						"Number Card",
						this.name
					);
				}
			},
		];
		this.set_card_actions(actions);
	}

	set_card_actions(actions) {
		this.card_actions = $(`<div class="card-actions dropdown pull-right">
			<a class="dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
				<button class="btn btn-default btn-xs"><span class="caret"></span></button>
			</a>
			<ul class="dropdown-menu" style="max-height: 300px; overflow-y: auto;">
				${actions.map(
					action =>
						`<li><a data-action="${action.action}">${
							action.label
						}</a></li>`
				)
				.join("")}
			</ul>
		</div>
		`);

		this.card_actions.find("a[data-action]").each((i, o) => {
			const action = o.dataset.action;
			$(o).click(actions.find(a => a.action === action));
		});
		this.action_area.html(this.card_actions);
	}
}
