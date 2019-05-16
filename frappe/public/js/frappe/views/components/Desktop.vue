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
					});
					const d = new frappe.ui.Dialog({
						title: __('Show / Hide Cards'),
						fields: fields.filter(f => f.options.length > 0),
						primary_action_label: __('Save'),
						primary_action: (values) => {
							d.hide();

							let modules_by_category = {};
							for (let category of this.module_categories) {
								let modules = values[category] || [];
								modules_by_category[category] = this.get_modules_for_category(category)
									.map(m => m.module_name)
									.filter(m => modules.includes(m));
							}

							frappe.call('frappe.desk.moduleview.update_modules_for_desktop', {
								modules_by_category
							}).then(r => this.update_desktop_settings(r.message));
						}
					});

					d.show();
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

