<template>
	<div class="modules-page-container" v-if="home_settings_fetched">
		<div
			class="modules-section"
			v-for="(category, i) in module_categories" :key="category"
		>
			<a
				v-if="i === 0"
				class="btn-show-hide text-muted text-medium"
				@click="show_hide_cards_dialog"
			>
				{{ __('Show / Hide Cards') }}
			</a>
			<desk-section
				v-if="get_modules_for_category(category)"
				:category="category"
				:modules="get_modules_for_category(category)"
				@update_home_settings="hs => update_modules_with_home_settings(hs)"
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
		let modules_list = frappe.boot.allowed_modules
			.filter(d => (d.type==='module' || d.category==='Places') && !d.blocked)
			.map(d => {
				d.links = (d.links || []).map(link => {
					link.route = generate_route(link);
					return link;
				});
				return d;
			});

		return {
			module_categories: ['Modules', 'Domains', 'Places', 'Administration'],
			modules: modules_list,
			home_settings_fetched: false
		};
	},
	created() {
		this.fetch_home_settings();
	},
	methods: {
		fetch_home_settings() {
			return frappe.db.get_value('User', user, 'home_settings')
				.then(r => {
					let home_settings = JSON.parse(r.message.home_settings || '{}');
					this.update_modules_with_home_settings(home_settings);
					this.home_settings_fetched = true;
				});
		},
		update_modules_with_home_settings(home_settings) {
			this.modules = this.modules.map(m => {
				let hidden_modules = home_settings.hidden_modules || [];
				m.hidden = hidden_modules.includes(m.module_name);

				let links = home_settings.links && home_settings.links[m.module_name];

				if (links) {
					links = JSON.parse(links);

					let default_links = m.links.map(link => link.name);
					m.links = m.links.map(link => {
						link.hidden = !links.includes(link.name);
						return link;
					});
					let new_links = links
						.filter(link => !default_links.includes(link))
						.filter(Boolean)
						.map(link => {
							let new_link = { name: link, label: link, type: 'doctype' };
							new_link.route = generate_route(new_link);
							return new_link;
						});
					m.links = m.links.concat(new_links);
				}

				return m;
			});
		},
		get_modules_for_category(category) {
			return this.modules.filter(m => m.category === category && !m.hidden);
		},
		show_hide_cards_dialog() {
			let fields = this.module_categories.map(category => {
				let modules = this.modules.filter(m => m.category === category);
				let options = modules.map(
					m => ({ label: m.label, value: m.module_name, checked: !m.hidden })
				);
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
				fields,
				primary_action_label: __('Save'),
				primary_action: (values) => {
					let all_modules = this.modules.map(m => m.module_name);
					let modules_to_show = Object.keys(values).map(k => values[k]).flatMap(m => m);
					let modules_to_hide = all_modules.filter(m => !modules_to_show.includes(m));
					d.hide();

					frappe.call('frappe.desk.moduleview.hide_modules_from_desktop', {
						modules: modules_to_hide
					})
					.then(r => r.message)
					.then(hs => this.update_modules_with_home_settings(hs));
				}
			});

			d.show();
		}
	}
}
</script>

<style lang="less" scoped>
.modules-page-container {
	margin-top: 40px;
	margin-bottom: 30px;
}

.modules-section {
	position: relative;
	padding-top: 30px;
}

.btn-show-hide {
	position: absolute;
	right: 0;
	top: 36px;
}

.toolbar-underlay {
	margin: 70px;
}
</style>

