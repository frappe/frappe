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
export default {
	props: ['category', 'all_modules'],
	components: {
		DeskModuleBox
	},
	data() {
		return {
			template_modules: this.all_modules,
			modules: this.all_modules.slice(),
			dragged_index: -1,
			hovered_index: -1,
		}
	},
	methods: {
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
		show_customize_dialog() {
			if(!this.dialog) {
				let all_modules = this.modules;
				let fields = [];

				const fieldname = 'home_settings';

				frappe.db.get_value('User', user, fieldname)
					.then((resp) => {
						let home_settings = JSON.parse(resp.message[fieldname]);
						let settings = home_settings[this.category];
						let selected_modules = Object.keys(settings);

						all_modules.forEach(module => {
							fields.push({
								label: __(module.module_name),
								fieldname: module.module_name,
								fieldtype: "Check",
								default: selected_modules.includes(module.module_name) ? 1 : 0
							});

							if(module.shortcuts) {
								fields.push({
									label: __(""),
									fieldname: module.module_name + "_shortcuts",
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
									default: module.shortcuts.map(m => (m.name || m.label)),
									depends_on: module.module_name
								});
							}
						});

						this.dialog = new frappe.ui.Dialog({
							title: __("Customize " + this.category),
							fields: fields,
							primary_action_label: __("Update"),
							primary_action: (values) => {
								let settings = {};
								this.template_modules.map((m, i) => {
									m.hidden = 0;
								})

								Object.keys(values).forEach(key => {
									if(!key.includes('shortcuts') && values[key]) {
										settings[key] = {
											links: values[key + '_shortcuts'] || []
										}
									}
									if(!values[key]) {
										this.template_modules.map((m, i) => {
											if(m.module_name === key) {
												m.hidden = 1;
											}
										})
									}
								});

								this.modules = this.template_modules.filter(m => !m.hidden);

								const user = frappe.session.user;
								const fieldname = 'home_settings';
								frappe.db.get_value('User', user, fieldname)
									.then((resp) => {
										let home_settings = JSON.parse(resp.message[fieldname]);
										home_settings[this.category] = settings;
										frappe.db.set_value('User', user, fieldname, home_settings)
											.then((resp) => {

												this.dialog.hide();
											})
											.fail((err) => {
												frappe.msgprint(err);
											});
									})
							}
						});

						this.dialog.modal_body.find('.clearfix').css({'display': 'none'});
						this.dialog.modal_body.find('.frappe-control*[data-fieldtype="MultiSelect"]').css({'margin-bottom': '30px'});

						this.dialog.show();

					});

			} else {
				this.dialog.show();
			}

		}
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

