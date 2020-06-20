import Widget from "./base_widget.js";
import { go_to_list_with_filters, shorten_number } from "./utils";

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
		this.make_card();
	}

	set_title() {
		$(this.title_field).html(`<div class="number-label">${this.card_doc.label}</div>`);
	}

	make_card() {
		frappe.model.with_doc('Number Card', this.name).then(card => {
			if (!card) {
				if (this.document_type) {
					frappe.run_serially([
						() => this.create_number_card(),
						() => this.render_card(),
					]);
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

	create_number_card() {
		this.set_doc_args();
		return frappe.xcall(
			'frappe.desk.doctype.number_card.number_card.create_number_card',
			{
				'args': this.card_doc
			}
		).then(doc => {
			this.name = doc.name;
			this.card_doc.stats_time_interval = doc.stats_time_interval;
			this.card_doc.name = this.name;
			this.widget.attr('data-widget-name', this.name);
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
		this.set_title();
		this.set_loading_state();

		frappe.run_serially([
			() => this.render_number(),
			() => this.render_stats(),
		]);
	}

	set_loading_state() {
		$(this.body).html(`<div class="number-card-loading text-muted">
			${__('Loading...')}
		</div>`);
	}

	get_number() {
		return frappe.xcall('frappe.desk.doctype.number_card.number_card.get_result', {
			doc: this.card_doc
		}).then(res => {
			this.number = res;
			if (this.card_doc.function !== 'Count') {
				return frappe.model.with_doctype(this.card_doc.document_type, () => {
					this.get_formatted_number();
				});
			} else {
				this.number_html = res;
			}
		});
	}

	get_formatted_number() {
		const based_on_df =
			frappe.meta.get_docfield(this.card_doc.document_type, this.card_doc.aggregate_function_based_on);
		const default_country = frappe.sys_defaults.country;
		const shortened_number = shorten_number(this.number, default_country);
		let number_parts = shortened_number.split(' ');

		const symbol = number_parts[1] || '';
		const formatted_number = $(frappe.format(number_parts[0], based_on_df)).text();

		this.number_html = formatted_number + ' ' + symbol;
	}

	render_number() {
		return this.get_number().then(() => {
			$(this.body).html(`<div class="widget-content">
				<div class="number" style="color:${this.card_doc.color}">${this.number_html}</div>
				</div>`);
		});
	}

	render_stats() {
		let caret_html ='';
		let color_class = '';

		return this.get_percentage_stats().then(() => {
			if (this.percentage_stat == undefined) return;

			if (this.percentage_stat == 0) {
				color_class = 'grey-stat';
			} else if (this.percentage_stat > 0) {
				caret_html = '<i class="fa fa-caret-up"></i>';
				color_class = 'green-stat';
			} else {
				caret_html = '<i class="fa fa-caret-down"></i>';
				color_class = 'red-stat';
			}

			const stats_qualifier_map = {
				'Daily': __('since yesterday'),
				'Weekly': __('since last week'),
				'Monthly': __('since last month'),
				'Yearly': __('since last year')
			};
			const stats_qualifier = stats_qualifier_map[this.card_doc.stats_time_interval];

			$(this.body).find('.widget-content').append(`<div class="card-stats ${color_class}">
				<span class="percentage-stat">
					${caret_html}
					${Math.abs(this.percentage_stat)} %
				</span>
				<span class="stat-period text-muted">
					${stats_qualifier}
				</span>
			</div>`);
		});
	}

	get_percentage_stats() {
		return frappe.xcall('frappe.desk.doctype.number_card.number_card.get_percentage_difference', {
			doc: this.card_doc,
			result: this.number
		}).then(res => {
			if (res !== undefined) {
				this.percentage_stat = +res.toFixed(2);
			}
		});
	}

	prepare_actions() {
		let actions = [
			{
				label: __('Refresh'),
				action: 'action-refresh',
				handler: () => {
					this.render_card();
				}
			},
			{
				label: __('Edit'),
				action: 'action-edit',
				handler: () => {
					frappe.set_route(
						'Form',
						'Number Card',
						this.name
					);
				}
			},
		];

		this.set_card_actions(actions);
	}

	set_card_actions(actions) {
		/* eslint-disable indent */
		this.card_actions =
			$(`<div class="card-actions dropdown pull-right">
				<a class="dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
					<button class="btn btn-default btn-xs"><span class="caret"></span></button>
				</a>
				<ul class="dropdown-menu" style="max-height: 300px; overflow-y: auto;">
					${actions
						.map(
							action =>
								`<li>
									<a data-action="${action.action}">${action.label}</a>
								</li>`
						).join('')}
				</ul>
			</div>`);
		/* eslint-disable indent */

		this.card_actions.find("a[data-action]").each((i, o) => {
			const action = o.dataset.action;
			$(o).click(actions.find(a => a.action === action));
		});

		this.action_area.html(this.card_actions);
	}
}
