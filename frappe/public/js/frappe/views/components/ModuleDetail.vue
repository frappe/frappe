<template>
	<div>
		<div v-if="sections.length" class="sections-container">
			<div v-for="section in sections"
				:key="section.label"
				class="border section-box"
			>
				<h4 class="h4"> {{ section.label }} </h4>
				<module-link-item v-for="item in section.items" class=" small"
					:key="section.label + item.label"
					:data-youtube-id="item.type==='help' ? item.youtube_id : false"
					v-bind="item"
				>
				</module-link-item>
			</div>
		</div>

		<div v-else class="sections-container">
			<div v-for="n in 3" :key="n" class="skeleton-section-box"></div>
		</div>
	</div>
</template>

<script>
import ModuleLinkItem from "./ModuleLinkItem.vue";

export default {
	components: {
		ModuleLinkItem
	},
	props: ['module_name', 'sections'],
	updated() {
		frappe.app.update_notification_count_in_modules();
	},
}
</script>
<style lang="less" scoped>
.sections-container {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
	column-gap: 15px;
	row-gap: 15px;
}

.section-box {
	padding: 5px 20px;
	border-radius: 4px;
}

.skeleton-section-box {
	background-color: #f5f7fa;
	height: 250px;
	border-radius: 4px;
}

.h4 {
	margin-bottom: 15px;
}

</style>
