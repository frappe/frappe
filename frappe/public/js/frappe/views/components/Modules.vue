<template>
	<div class="modules-page-container">
		<module-detail v-if="this.route && modules_list.map(m => m.module_name).includes(route[1])" :module_name="route[1]" :sections="current_module_sections"></module-detail>
	</div>
</template>

<script>
import ModuleDetail from './ModuleDetail.vue';

export default {
	components: {
		ModuleDetail
	},
	data() {
		return {
			route: frappe.get_route(),
			current_module_label: '',
			current_module_sections: [],
			modules_data_cache: {},
			modules_list: frappe.boot.allowed_modules
				.filter(d => (d.type==='module' || d.category==='Places') && !d.blocked),
		};
	},
	created() {
		this.update_current_module();
	},
	mounted() {
		frappe.module_links = {};
		frappe.route.on('change', () => {
			this.update_current_module();
		});
	},
	methods: {
		update_current_module() {
			let route = frappe.get_route();
			if(route[0] === 'modules' || !route[0]) {
				this.route = route;
				let module = this.modules_list.filter(m => m.module_name == route[1])[0];
				let module_name = module && (module.label || module.module_name);
				let title = this.current_module_label ? this.current_module_label : module_name;

				frappe.modules.home && frappe.modules.home.page.set_title(title);

				if(!frappe.modules.home) {
					setTimeout(() => {
						frappe.modules.home.page.set_title(title);
					}, 200);
				}

				if(module_name) {
					this.get_module_sections(module.module_name);
				}
			}
		},

		get_module_sections(module_name) {
			let cache = this.modules_data_cache[module_name];
			if(cache) {
				this.current_module_sections = cache;
			} else {
				this.current_module_sections = [];
				return frappe.call({
					method: "frappe.desk.moduleview.get",
					args: {
						module: module_name,
					},
					callback: (r) => {
						var m = frappe.get_module(module_name);
						this.current_module_sections = r.message.data;
						this.process_data(module_name, this.current_module_sections);
						this.modules_data_cache[module_name] = this.current_module_sections;
					},
					freeze: true,
				});
			}
		},
		process_data(module_name, data) {
			frappe.module_links[module_name] = [];
			data.forEach(function(section) {
				section.items.forEach(function(item) {
					item.style = '';
					if(item.type==="doctype") {
						item.doctype = item.name;

						// map of doctypes that belong to a module
						frappe.module_links[module_name].push(item.name);
					}
					if(!item.route) {
						if(item.link) {
							item.route=strip(item.link, "#");
						}
						else if(item.type==="doctype") {
							if(frappe.model.is_single(item.doctype)) {
								item.route = 'Form/' + item.doctype;
							} else {
								if (item.filters) {
									frappe.route_options=item.filters;
								}
								item.route="List/" + item.doctype;
								//item.style = 'font-weight: 500;';
							}
							// item.style = 'font-weight: bold;';
						}
						else if(item.type==="report" && item.is_query_report) {
							item.route="query-report/" + item.name;
						}
						else if(item.type==="report") {
							item.route="List/" + item.doctype + "/Report/" + item.name;
						}
						else if(item.type==="page") {
							item.route=item.name;
						}

						item.route = '#' + item.route;
					}

					if(item.route_options) {
						item.route += "?" + $.map(item.route_options, function(value, key) {
							return encodeURIComponent(key) + "=" + encodeURIComponent(value); }).join('&');
					}

					if(item.type==="page" || item.type==="help" || item.type==="report" ||
					(item.doctype && frappe.model.can_read(item.doctype))) {
						item.shown = true;
					}
				});
			});
		}
	}
}
</script>

<style lang="less" scoped>
.modules-page-container {
	margin: 15px 0px;
}

</style>
