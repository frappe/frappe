import { generate_route } from './utils';
import Widget from './base_widget.js'

export default class LinkWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	get_link() {
		return this.module_data.type === 'module'
			? '#modules/' + this.module_data.module_name
			: this.module_data.link
	}

	make_widget() {
		this.widget = $(`<div class="border module-box" data-module-name="${this.module_data.module_name}" tab-index="10">
			<div class="flush-top">
				<div class="module-box-content">
					<div class="level module-box-content-wrapper">
						<a class="module-box-link" href="${this.get_link()}">
							<h4 class="h4">
							<div>
								<i class="${this.module_data.icon}" style="color:#8d99a6;font-size:18px;margin-right:6px;"></i>
								${this.module_data.label}
							</div>
							</h4>
						</a>
					</div>
				</div>
			</div>
		</div>`);
	}
}