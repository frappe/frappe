<template>
	<div class="modules-page-container">
		<module-detail
			v-if="
				this.route && modules_list.map(m => m.module_name).includes(route[1])
			"
			:module_name="route[1]"
			:sections="current_module_sections"
		></module-detail>
	</div>
</template>

<script>
import ModuleDetail from './ModuleDetail.vue'
import { generate_route } from './utils.js'

export default {
	components: {
		ModuleDetail,
	},
	data() {
		return {
			route: frappe.get_route(),
			current_module_label: '',
			current_module_sections: [],
			modules_data_cache: {},
			modules_list: frappe.boot.allowed_modules.filter(
				d => (d.type === 'module' || d.category === 'Places') && !d.blocked
			),
		}
	},
	created() {
		this.update_current_module()
	},
	mounted() {
		frappe.module_links = {}
		frappe.route.on('change', () => {
			this.update_current_module()
		})
	},
	methods: {
		update_current_module() {
			let route = frappe.get_route()
			if (route[0] === 'modules') {
				this.route = route
				let module = this.modules_list.filter(m => m.module_name == route[1])[0]
				let module_name = module && (module.label || module.module_name)
				let title = this.current_module_label ? this.current_module_label : module_name;
				let is_enabled = this.is_enabled(module.module_name, frappe.enabled_modules.modules);

				frappe.modules.home && frappe.modules.home.page.set_title(title);
				this.setup_enable_module(is_enabled, module)

				if (!frappe.modules.home) {
					setTimeout(() => {
						frappe.modules.home.page.set_title(title)
						this.setup_enable_module(is_enabled, module)
					}, 200)
				}

				if (module_name) {
					this.get_module_sections(module.module_name)
				}
			}
		},
		get_module_sections(module_name) {
			let cache = this.modules_data_cache[module_name]
			if (cache) {
				this.current_module_sections = cache
			} else {
				this.current_module_sections = []
				return frappe.call({
					method: 'frappe.desk.moduleview.get',
					args: {
						module: module_name,
					},
					callback: r => {
						var m = frappe.get_module(module_name)
						this.current_module_sections = r.message.data
						this.process_data(module_name, this.current_module_sections)
						this.modules_data_cache[module_name] = this.current_module_sections
					},
					freeze: true,
				})
			}
		},
		process_data(module_name, data) {
			frappe.module_links[module_name] = []
			data.forEach(function(section) {
				section.items.forEach(function(item) {
					item.route = generate_route(item)
				})
			})
		},
		is_enabled(module_name, enabled_modules) {
			if (enabled_modules.indexOf(module_name) === -1) {
				return false
			}
			return true
		},
		setup_enable_module(is_enabled, module) {
			if (!module || is_enabled) {
				return
			}
			frappe.modules.home && frappe.modules.home.page.set_indicator('Module Disabled', 'red')
			frappe.modules.home && frappe.modules.home.page.set_secondary_action('Enable Module', () => {
				frappe.show_alert({
					message: __('Enabling Module.'),
					indicator: 'red'
				});
				frappe.call({
					method: 'frappe.core.doctype.module_def.module_def.enable_module',
					args: {
						module: module.module_name
					},
					callback: r => {
						frappe.enabled_modules.modules = $.extend([], r.message);
						frappe.show_alert({
							message: __('Module Enabled.'),
							indicator: 'green'
						})
					}
				})
			});
		}
	},
}
</script>

<style lang="less" scoped>
.modules-page-container {
	margin: 15px 0px;
}
</style>
