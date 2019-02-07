<template>
	<div class="modules-page-container">
		<div v-for="category in module_categories"
			:key="category">

			<div v-if="modules.filter(m => m.category === category).length" class="module-category h6 uppercase">
				{{ category }}
			</div>

			<div class="modules-container">
				<a v-for="module in modules.filter(m => m.category === category )"
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
							<p class="small text-muted"> {{ module.description }} </p>
						</div>
					</div>
				</a>
			</div>

		</div>

	</div>
</template>

<script>

export default {
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
	margin: 70px 0px;
}

.module-category {
	margin-top: 30px;
	margin-bottom: 15px;
	border-bottom: 1px solid #d0d8dd;
}

.modules-container {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
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
	padding-right: 15px;
	flex: 1;

	h4 {
		margin-bottom: 5px
	}

	p {
		margin-top: 5px;
		font-size: 80%;
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

</style>

