import { generate_route } from './utils';
import Widget from './base_widget.js'

export default class ModuleWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	get_link() {
		return this.module_data.type === 'module'
			? '#modules/' + this.module_data.module_name
			: this.module_data.link
	}

	make_widget() {
		this.widget = $(`<div class="border module-box" data-module-name="${this.module_data.module_name}">
			<div class="flush-top">
				<div class="module-box-content">
					<div class="level">
						<a class="module-box-link" href="${this.get_link()}">
							<h4 class="h4">
							<div>
								<i class="${this.module_data.icon}" style="color:#8d99a6;font-size:18px;margin-right:6px;"></i>
								${this.module_data.label}
							</div>
							</h4>
						</a>
						${this.module_data.type === 'module' ? this.make_dropdown(): ''}
					</div>
				</div>
			</div>
		</div>`);
		this.dropdown_button = this.widget.find('.octicon-chevron-down');
		this.dropdown_body = this.widget.find('.dropdown-body');

		this.widget.appendTo(this.container);
	}

	make_dropdown() {
		const list_html = this.module_data.links.map(item => {
			return `<li class="${item.class || null}">
					<a class="list-item" href="${generate_route(item)}">${item.label}</a>
				</li>`
		})

		return `<div class="inline-block relative">
					<div>
						<span class="pull-right">
							<i class="octicon octicon-chevron-down text-muted"></i>
						</span>
					</div>
					<div class="absolute mt-default z-20 pin-r dropdown-body" style="display: none;">
						<ul class="list-reset border">
							${list_html.join(' ')}
							<li class="border-top"><div class="list-item">Customize</div></li>
						</ul>
					</div>
				</div>`
	}

	setup_events() {
		this.setup_dropdown_events();
	}

	setup_dropdown_events() {
		this.dropdown_button.on('click', (event) => {
			this.dropdown_body.toggle();
			event.stopPropagation();
		})

		$(window).click(() => {
			this.dropdown_body.hide();
		});
	}
}