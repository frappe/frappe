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
					let module_options = r.message;
					let fields = this.module_categories.map(category => {
						let options = module_options.filter(m => m.category === category);
						return {
							label: category,
							fieldname: category,
							fieldtype: 'MultiCheck',
							options,
							columns: 2
						}
					}).filter(f => f.options.length > 0);

					let old_values = null;

					const d = new frappe.ui.Dialog({
						title: __('Show / Hide Cards'),
						fields: fields,
						primary_action_label: __('Save'),
						primary_action: (values) => {

							let category_map = {};
							for (let category of this.module_categories) {
								let old_modules = old_values[category] || [];
								let new_modules = values[category] || [];

								let removed = old_modules.filter(module => !new_modules.includes(module));
								let added = new_modules.filter(module => !old_modules.includes(module));

								category_map[category] = { added, removed };
 							}

							frappe.call({
								method: 'frappe.desk.moduleview.update_hidden_modules',
								args: { category_map },
								btn: d.get_primary_btn()
							}).then(r => {
								this.update_desktop_settings(r.message)
								d.hide();
							});
						}
					});

					d.show();

					// deepcopy
					old_values = JSON.parse(JSON.stringify(d.get_values()));
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

