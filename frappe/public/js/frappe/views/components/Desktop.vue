<template>
	<div class="modules-page-container">
		<div class="toolbar-underlay"></div>
		<div v-for="category in module_categories"
			:key="category">

			<desk-section
				v-if="modules.filter(m => m.category === category).length"
				:category="category"
				:all_modules="modules.filter(m => m.category === category)"
			>
			</desk-section>

		</div>

	</div>
</template>

<script>
import DeskSection from './DeskSection.vue';

export default {
	components: {
		DeskSection
	},
	data() {
		let modules_list = frappe.boot.allowed_modules
			.filter(d => (d.type==='module' || d.category==='Places') && !d.blocked);

		modules_list.forEach(module => {
			module.count = this.get_module_count(module.module_name);
		});

		return {
			route_str: frappe.get_route()[1],
			module_label: '',
			module_categories: ["Modules", "Domains", "Places", "Administration"],
			modules: modules_list
		};
	},
	methods: {
		get_module_count(module_name) {
			var module_doctypes = frappe.boot.notification_info.module_doctypes[module_name];
			var sum = 0;

			if(module_doctypes && frappe.boot.notification_info.open_count_doctype) {
				// sum all doctypes for a module
				for (var j=0, k=module_doctypes.length; j < k; j++) {
					var doctype = module_doctypes[j];
					let count = (frappe.boot.notification_info.open_count_doctype[doctype] || 0);
					count = typeof count == "string" ? parseInt(count) : count;
					sum += count;
				}
			}

			if(frappe.boot.notification_info.open_count_doctype
				&& frappe.boot.notification_info.open_count_doctype[module_name]!=null) {
				// notification count explicitly for doctype
				let count = frappe.boot.notification_info.open_count_doctype[module_name] || 0;
				count = typeof count == "string" ? parseInt(count) : count;
				sum += count;
			}

			if(frappe.boot.notification_info.open_count_module
				&& frappe.boot.notification_info.open_count_module[module_name]!=null) {
				// notification count explicitly for module
				let count = frappe.boot.notification_info.open_count_module[module_name] || 0;
				count = typeof count == "string" ? parseInt(count) : count;
				sum += count;
			}

			sum = sum > 99 ? "99+" : sum;

			return sum;
		}
	}
}
</script>

<style lang="less" scoped>
.modules-page-container {
	margin-bottom: 30px;
}

.toolbar-underlay{
	margin: 70px;
}

</style>

