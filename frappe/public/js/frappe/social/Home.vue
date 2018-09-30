<template>
	<div class="social">
		<component :is="current_page"></component>
	</div>
</template>

<script>

import Wall from './pages/Wall.vue';
import Profile from './pages/Profile.vue';
import NotFound from './components/NotFound.vue';

function get_route_map() {
	return {
		'social/home': Wall,
		'social/profile': Profile
	}
}

export default {
	data() {
		return {
			current_page: this.get_current_page()
		}
	},
	mounted() {
		frappe.route.on('change', () => {
			if (frappe.get_route()[0] === 'social') {
				this.set_current_page();
				frappe.utils.scroll_to(0);
			}
		});
	},
	methods: {
		set_current_page() {
			this.current_page = this.get_current_page();
		},
		get_current_page() {
			const route_map = get_route_map();
			const route = frappe.get_route_str();
			if (route_map[route]) {
				return route_map[route];
			}
			return NotFound;
		}
	}
}
</script>
