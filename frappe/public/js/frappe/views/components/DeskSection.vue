<template>
  <div>
    <div class="section-header level text-muted">
      <div class="module-category h6 uppercase">{{ __(this.category) }}</div>
    </div>

    <div class="modules-container" :class="{'dragging': dragging}" ref="modules-container">
      <desk-module-box
        v-for="(module, index) in modules"
        :key="module.module_name"
        :index="index"
        v-bind="module"
		@customize="show_module_card_customize_dialog(module)"
      ></desk-module-box>
    </div>
  </div>
</template>

<script>
import DeskModuleBox from "./DeskModuleBox.vue";

export default {
	props: ['category', 'modules'],
	components: {
		DeskModuleBox
	},
	data() {
		return {
			dragging: false,
			fetched_module_links: {}
		}
	},
	mounted() {
		if (!frappe.utils.is_mobile()) {
			this.setup_sortable();
		}
	},
	methods: {
		setup_sortable() {
			let modules_container =this.$refs['modules-container'];
			this.sortable = new Sortable(modules_container, {
				animation: 150,
				onStart: () => this.dragging = true,
				onEnd: () => {
					this.dragging = false;
					let modules = Array.from(modules_container.querySelectorAll('.module-box'))
						.map(node => node.dataset.moduleName);

					this.$emit('module-order-change', {
						module_category: this.category,
						modules
					});
				}
			})
		},
		show_module_card_customize_dialog(module) {
			const me = this;
			const d = new frappe.ui.Dialog({
				title: __('Customize Shortcuts'),
				fields: [
					{
						label: __('Shortcuts'),
						fieldname: 'links',
						fieldtype: 'MultiSelectPills',
						get_data: () => {
							const module_links = me.fetched_module_links[module.module_name];
							if (!module_links) {
								return frappe.xcall('frappe.desk.moduleview.get_links_for_module', {
									app: module.app,
									module: module.module_name,
								}).then(links => {
									me.fetched_module_links[module.module_name] = links;
									return links;
								});
							} else {
								return module_links;
							}
						},
						default: module.links.filter(l => !l.hidden).map(l => l.name)
					}
				],
				primary_action_label: __('Save'),
				primary_action: ({ links }) => {
					frappe.call('frappe.desk.moduleview.update_links_for_module', {
						module_name: module.module_name,
						links: links || []
					}).then(r => {
						this.$emit('update-desktop-settings', r.message);
					});
					d.hide();
				}
			});

			d.show();
		},
	}
}
</script>

<style lang="less" scoped>
.modules-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  grid-auto-rows: minmax(62px, 1fr);
  column-gap: 15px;
  row-gap: 15px;
  align-items: center;
}
</style>
