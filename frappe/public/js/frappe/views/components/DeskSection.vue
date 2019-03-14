<template>
  <div>
    <div class="section-header level text-muted">
      <div class="module-category h6 uppercase">{{ category }}</div>

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
      ></desk-module-box>
    </div>
  </div>
</template>

<script>
import DeskModuleBox from "./DeskModuleBox.vue";
import { generate_route } from "./utils.js";

export default {
	props: ['category', 'all_modules', 'customization_settings'],
	components: {
		DeskModuleBox
	},
	data() {
		let default_modules = this.all_modules;
		let modules = this.get_customized_modules(default_modules, this.customization_settings);

		return {
			default_modules: default_modules,
			modules: modules,
			new_settings: {},
			dragged_index: -1,
			hovered_index: -1,
		}
	},
	methods: {
		show_customize_dialog() {
			if(!this.dialog) {
				const fields = this.make_fields();
				this.make_and_show_dialog(fields);
			} else {
				this.dialog.show();
			}
		},
		make_fields() {
			let fields = [];
			this.modules.forEach(module => {
				fields.push(this.get_module_select_field(module));

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
					this.update_settings(values);
				}
			});

			this.dialog.modal_body.find('.clearfix').css({'display': 'none'});
			this.dialog.modal_body.find('.frappe-control*[data-fieldtype="MultiSelect"]').css({'margin-bottom': '30px'});

			this.dialog.show();
		},

		update_settings(values) {
			// Figure out the diff from the default settings known from modules
			let new_settings = {};
			const checkbox_fields = Object.keys(values).filter(f => !f.includes('links'));

			checkbox_fields.forEach(module_name => {
				const default_module = this.default_modules.filter(f => f.module_name === module_name)[0];

				// Check if hidden changed
				const default_hidden = default_module.hidden ? 1 : 0;
				const new_hidden = !values[module_name] ? 1 : 0;
				const hidden_changed = new_hidden != default_hidden;

				// Check if links changed
				let links_changed = 0;
				let new_links = [];

				if(!new_hidden) {
					const default_links = default_module.links.map(l => (l.name || l.label));
					const new_links_str = values[module_name + '_links'] || '';
					new_links = new_links_str ? new_links_str.split(",") : [];
					links_changed = !this.are_arrays_equal(new_links, default_links);
				}

				// Make new settings
				let new_module_settings;

				if(hidden_changed || links_changed) {
					new_module_settings = {};
					if(hidden_changed) {
						new_module_settings.hidden = new_hidden;
					}
					if(links_changed) {
						new_module_settings.links = new_links;
					}
				}

				if(new_module_settings) {
					new_module_settings.app = this.default_modules.filter(m => m.module_name === module_name)[0].app;
					new_settings[module_name] = new_module_settings;
				}
			});

			if(Object.keys(new_settings)) {
				frappe.call({
					type: "GET",
					method:'frappe.desk.moduleview.update_desk_section_settings',
					freeze: true,
					args: {
						desk_section: this.category,
						new_settings: new_settings
					},
					callback: (r) => {
						let new_settings_with_link_objects = r.message;
						let home_settings = JSON.parse(frappe.boot.home_settings);
						home_settings[this.category] = new_settings_with_link_objects;
						frappe.boot.home_settings = JSON.stringify(home_settings);

						this.modules = this.get_customized_modules(this.default_modules, new_settings_with_link_objects);
						this.dialog.hide();
					}
				});
			} else {
				this.dialog.hide();
			};
		},

		get_customized_modules(default_modules, customization_settings={}) {
			return default_modules.map(module => {
				let customized_module = JSON.parse(JSON.stringify(module));

				const module_settings = customization_settings[module.module_name];
				if(module_settings) {
					if(module_settings.links) {
						customized_module.links = module_settings.links;
					}
					customized_module.hidden = module_settings ? module_settings.hidden : 0;
				}

				if(customized_module.links) {
					customized_module.links.forEach(link => {
						link.route = generate_route(link);
					});
				}

				return customized_module;
			});
		},

		get_module_select_field(module) {
			return {
				label: __(module.module_name),
				fieldname: module.module_name,
				fieldtype: "Check",
				default: module.hidden ? 0 : 1
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
				default: module.links.map(l => (l.name || l.label)),
				depends_on: module.module_name
			};
		},

		are_arrays_equal(arr1, arr2) {
			if(arr1.length !== arr2.length) return false;
			let areEqual = true;
			arr1.map((d, i) => {
				if(arr2[i] !== d) areEqual = false;
			});
			return areEqual;
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
  grid-auto-rows: minmax(62px, 1fr);
  column-gap: 15px;
  row-gap: 15px;
  align-items: center;
}
</style>

