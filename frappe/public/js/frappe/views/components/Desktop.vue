<template>
	<div class="modules-page-container" v-if="home_settings_fetched">
		<a
			class="btn-show-hide text-muted text-medium"
			@click="show_hide_cards_dialog"
		>
			{{ __('Show / Hide Cards') }}
		</a>
		<div
			class="modules-section"
			v-for="(category, i) in module_categories" :key="category"
		>
			<desk-section
				v-if="get_modules_for_category(category).length"
				:category="category"
				:modules="get_modules_for_category(category)"
				@update-desktop-settings="update_desktop_settings"
				@module-order-change="update_module_order"
			>
			</desk-section>
		</div>
	</div>
</template>

<script>
import DeskSection from './DeskSection.vue';
import { generate_route } from './utils';

export default {
	components: {
		DeskSection
	},
	data() {
		return {
			module_categories: ['Modules', 'Domains', 'Places', 'Administration'],
			modules: [],
			home_settings_fetched: false
		};
	},
	created() {
		this.fetch_desktop_settings();
	},
	methods: {
		fetch_desktop_settings() {
			frappe.call('frappe.desk.moduleview.get_desktop_settings')
				.then(r => {
					if (r.message) {
						this.update_desktop_settings(r.message);
						this.home_settings_fetched = true;
					}
				});
		},
		update_desktop_settings(desktop_settings) {
			this.modules = this.add_routes_for_module_links(desktop_settings);
		},
		add_routes_for_module_links(user_settings) {
			for (let category in user_settings) {
				user_settings[category] = user_settings[category].map(m => {
					m.links = (m.links || []).map(link => {
						link.route = generate_route(link);
						return link;
					});
					return m;
				});
			}
			return user_settings;
		},
		update_module_order({ module_category, modules }) {
			frappe.call('frappe.desk.moduleview.update_modules_order', { module_category, modules });
		},
		get_modules_for_category(category) {
			return this.modules[category] || [];
		},
		show_hide_cards_dialog() {
			frappe.call('frappe.desk.moduleview.get_options_for_show_hide_cards')
				.then(r => {
					let { user_options, global_options } = r.message;

					let user_value = `User (${frappe.session.user})`
					let fields = [
						{
							label: __('Setup For'),
							fieldname: 'setup_for',
							fieldtype: 'Select',
							options: [
								{
									label: __('User ({0})', [frappe.session.user]),
									value: user_value
								},
								{
									label: __('Everyone'),
									value: 'Everyone'
								}
							],
							default: user_value,
							depends_on: doc => frappe.user_roles.includes('System Manager'),
							onchange() {
								let value = d.get_value('setup_for');
								let field = d.get_field('setup_for');
								let description = value === 'Everyone' ? __('Hide cards for all users') : '';
								field.set_description(description);
							}
						}
					];

					let user_section = this.module_categories.map(category => {
						let options = user_options.filter(m => m.category === category);
						return {
							label: category,
							fieldname: `user:${category}`,
							fieldtype: 'MultiCheck',
							options,
							columns: 2
						}
					}).filter(f => f.options.length > 0);

					user_section = [
						{
							fieldname: 'user_section',
							fieldtype: 'Section Break',
							depends_on: doc => doc.setup_for === user_value
						}
					].concat(user_section);

					let global_section = this.module_categories.map(category => {
						let options = global_options.filter(m => m.category === category);
						return {
							label: category,
							fieldname: `global:${category}`,
							fieldtype: 'MultiCheck',
							options,
							columns: 2
						}
					}).filter(f => f.options.length > 0);

					global_section = [
						{
							fieldname: 'global_section',
							fieldtype: 'Section Break',
							depends_on: doc => doc.setup_for === 'Everyone'
						}
					].concat(global_section);

					fields = fields.concat(user_section, global_section);

					let old_values = null;
					const d = new frappe.ui.Dialog({
						title: __('Show / Hide Cards'),
						fields: fields,
						primary_action_label: __('Save'),
						primary_action: (values) => {
							if (values.setup_for === 'Everyone') {
								this.update_global_modules(d);
							} else {
								this.update_user_modules(d, old_values);
							}
						}
					});

					d.show();

					// deepcopy
					old_values = JSON.parse(JSON.stringify(d.get_values()));
				});
		},

		update_user_modules(d, old_values) {
			let new_values = d.get_values();
			let category_map = {};
			for (let category of this.module_categories) {
				let old_modules = old_values[`user:${category}`] || [];
				let new_modules = new_values[`user:${category}`] || [];

				let removed = old_modules.filter(module => !new_modules.includes(module));
				let added = new_modules.filter(module => !old_modules.includes(module));

				category_map[category] = { added, removed };
			}

			frappe.call({
				method: 'frappe.desk.moduleview.update_hidden_modules',
				args: { category_map },
				btn: d.get_primary_btn()
			}).then(r => {
				this.update_desktop_settings(r.message);
				d.hide();
			});
		},

		update_global_modules(d) {
			let blocked_modules = [];
			for (let category of this.module_categories) {
				let field = d.get_field(`global:${category}`);
				if (field) {
					let unchecked_options = field.get_unchecked_options();
					blocked_modules = blocked_modules.concat(unchecked_options);
				}
			}

			frappe.call({
				method: 'frappe.desk.moduleview.update_global_hidden_modules',
				args: {
					modules: blocked_modules
				},
				btn: d.get_primary_btn()
			}).then(r => {
				this.update_desktop_settings(r.message);
				d.hide();
			});
		}
	}
}
</script>

<style lang="less" scoped>
.modules-page-container {
	position: relative;
	margin-top: 40px;
	margin-bottom: 30px;
	padding-top: 1px;
}

.modules-section {
	position: relative;
	margin-top: 30px;
}

.btn-show-hide {
	position: absolute;
	right: 0;
	top: 39px;
	z-index: 1;
}

.toolbar-underlay {
	margin: 70px;
}
</style>

