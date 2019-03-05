<template>
	<div>
		<div class="section-header level text-muted">
			<div class="module-category h6 uppercase">
			{{ category }}
			</div>

			<div>
				<a class="small text-muted" @click="show_customize_dialog">{{ __("Customize") }}</a>
			</div>
		</div>

		<div class="modules-container">
			<desk-module-box
				v-for="(module, index) in modules.filter(m => !m.hidden)"
				:key="module.name"
				:index="index"
				v-bind="module"

				@box-dragstart="box_dragstart($event)"
				@box-dragend="box_dragend($event)"
				@box-enter="box_enter($event)"
				@box-drop="box_drop($event)"
			>
			</desk-module-box>
		</div>
	</div>
</template>

<script>
import DeskModuleBox from "./DeskModuleBox.vue";
import { generate_route } from './utils.js';

export default {
	props: ['category', 'all_modules'],
	components: {
		DeskModuleBox
	},
	data() {
		let template_modules = this.all_modules;
		template_modules.forEach(module => {
			if(module.links) {
				module.links.forEach(link => {
					link.route = generate_route(link);
				});
			}
		});

		return {
			template_modules: template_modules,
			modules: template_modules.slice(),
			settings: {},
			all_settings: {},
			dragged_index: -1,
			hovered_index: -1,
		}
	},
	methods: {
		show_customize_dialog() {
			if(!this.dialog) {
				this.get_settings()
					.then(() => {
						const fields = this.make_fields();
						this.make_and_show_dialog(fields);
					});
			} else {
				this.dialog.show();
			}
		},
		get_settings() {
			return frappe.db.get_value('User', user, 'home_settings')
				.then(resp => {
					this.all_settings = JSON.parse(resp.message['home_settings']);
					this.settings = this.all_settings[this.category];
				});
		},
		make_fields() {
			let fields = [];
			let template_modules = this.template_modules;
			let selected_modules = Object.keys(this.settings);

			template_modules.forEach(module => {
				fields.push(this.get_module_select_field(module, selected_modules));

				if(module.links) {
					fields.push(this.get_links_multiselect_field(module));
				}
			});

			return fields;
		},
		make_and_show_dialog(fields) {
			this.dialog = new frappe.ui.Dialog({
				title: __("Customize " + this.category),
				fields: fields,
				primary_action_label: __("Update"),
				primary_action: (values) => {
					let module_link_list_map = {};

					Object.keys(values).forEach(module_name => {
						if(!module_name.includes('links') && values[module_name]) {
							const links_str = values[module_name + '_links'] || '';
							this.settings[module_name]["links"] = links_str;
							if(values[module_name]) {
								module_link_list_map[module_name] = {
									links: links_str.split(","),
									app: this.template_modules.filter(m => m.module_name === module_name)[0].app
								};
							}
						}
					});

					frappe.db.set_value('User', user, 'home_settings', this.all_settings)
						.then((resp) => {
							this.update_modules(module_link_list_map);
							this.dialog.hide();
						})
						.fail((err) => {
							frappe.msgprint(err);
						});
				}
			});

			this.dialog.modal_body.find('.clearfix').css({'display': 'none'});
			this.dialog.modal_body.find('.frappe-control*[data-fieldtype="MultiSelect"]').css({'margin-bottom': '30px'});

			this.dialog.show();
		},

		update_modules(module_link_list_map) {
			frappe.call({
				type: "GET",
				method:'frappe.desk.moduleview.get_module_link_items_from_dict',
				freeze: true,
				args: {
					module_link_list_map: module_link_list_map
				},
				callback: (r) => {
					const module_links_dict = r.message;
					this.template_modules.map((m, i) => {
						let raw_links = module_links_dict[m.module_name];
						raw_links.forEach(link => {
							link.route = generate_route(link);
						});
						if(Object.keys(module_link_list_map).includes(m.module_name)) {
							m.hidden = 0;
							m.links = raw_links;
						} else {
							m.hidden = 1;
						}
					});

					this.modules = this.template_modules.filter(m => !m.hidden);
				}
			});
		},

		get_module_select_field(module, selected_modules) {
			return {
				label: __(module.module_name),
				fieldname: module.module_name,
				fieldtype: "Check",
				default: selected_modules.includes(module.module_name) ? 1 : 0
			}
		},

		get_links_multiselect_field(module) {
			return {
				label: __(""),
				fieldname: module.module_name + "_links",
				fieldtype: "MultiSelect",
				get_data: function() {
					let data = [];

					frappe.call({
						type: "GET",
						method:'frappe.desk.moduleview.get_links',
						async: false,
						no_spinner: true,
						args: {
							app: module.app,
							module: module.module_name,
						},
						callback: function(r) {
							data = r.message;
						}
					});
					return data;
				},
				default: module.links.map(m => (m.name || m.label)),
				depends_on: module.module_name
			};
		},

		box_dragstart(index) {
			this.dragged_index = index;
		},

		box_dragend(index) {
			this.dragged_index = -1;
			this.hovered_index = -1;
		},

		box_enter(index) {
			this.hovered_index = index;
		},

		box_drop(index) {
			let d = this.dragged_index;
			let h = this.hovered_index;
			if (d < h) {
				this.modules.splice(h, 0, this.modules[d]);
				this.modules.splice(d, 1);
			}
		},
	}
}
</script>

<style lang="less" scoped>
.section-header {
	margin-top: 30px;
	margin-bottom: 15px;
	border-bottom: 1px solid #d0d8dd;
}

.modules-container {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
	grid-auto-rows: minmax(72px, 1fr);
	column-gap: 15px;
	row-gap: 15px;
}
</style>

