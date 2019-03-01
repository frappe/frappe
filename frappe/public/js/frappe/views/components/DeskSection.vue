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
			<a v-for="module in modules"
				:key="module.name"
				:href="module.type === 'module' ? '#modules/' + module.module_name : module.link"
				class="border module-box"
			>
				<div class="flush-top">
					<div class="module-box-content">
						<h4 class="h4">
							<span class="indicator" :class="module.count ? 'red' : (module.onboard_present ? 'orange' : 'grey')"></span>
							{{ module.label }}
						</h4>
						<p
							v-if="module.shortcuts.length"
							class="small text-muted">
								<a
									v-for="shortcut in module.shortcuts"
									:key="shortcut.name"
									:href="shortcut.link"
									class="btn btn-default btn-xs shortcut-tag" title="toggle Tag"> {{ shortcut.label }}
								</a>
						</p>
						<p v-else class="small text-muted"> {{ module.description }} </p>
					</div>
				</div>
			</a>
		</div>
	</div>
</template>

<script>
export default {
	props: ['category', 'initial_modules'],
	data() {
		return {
			modules: this.initial_modules
		}
	},
	methods: {
		show_customize_dialog() {

			if(!this.dialog) {
				let all_modules = this.modules;
				let fields = [];

				all_modules.forEach(module => {
					fields.push({
						label: __(module.module_name),
						fieldname: module.module_name,
						fieldtype: "Check",
						default: 1
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
						Object.keys(values).forEach(key => {
							if(!key.includes('shortcuts') && values[key]) {
								settings[key] = {
									links: values[key + '_shortcuts'] || []
								}
							}
							if(!values[key]) {
								let index = -1;
								this.modules.map((m, i) => {
									if(m.module_name === key) {
										index = i;
									}
								})
								this.modules.splice(index, 1);
							}
						});

						const user = frappe.session.user;
						const fieldname = 'home_settings';
						frappe.db.get_value('User', user,fieldname)
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
			}

			this.dialog.show();
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

.module-box {
	border-radius: 4px;
	cursor: pointer;
	padding: 5px 15px;
	padding-top: 3px;
	display: block;
}

.module-box:hover {
	background-color: #fafbfc;
	text-decoration: none;
}

.module-box-content {
	width: 100%;

	h4 {
		margin-bottom: 5px
	}

	p {
		margin-top: 5px;
		font-size: 80%;
		display: flex;
		overflow: hidden;
	}
}

.icon-box {
	padding: 15px;
	width: 54px;
	display: flex;
	justify-content: center;
}

.icon {
	font-size: 24px;
}

.open-notification {
	top: -2px;
}

.shortcut-tag {
	margin-right: 5px;
}
</style>

