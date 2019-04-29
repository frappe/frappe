<template>
	<div ref="social" class="social">
		<keep-alive>
			<component :is="current_page.component" v-bind="current_page.props"></component>
		</keep-alive>
		<image-viewer :src="preview_image_src" v-if="show_preview"></image-viewer>
	</div>
</template>

<script>

import Wall from './pages/Wall.vue';
import Profile from './pages/Profile.vue';
import UserList from './pages/UserList.vue';
import NotFound from './components/NotFound.vue';
import ImageViewer from './components/ImageViewer.vue';

function get_route_map() {
	return {
		'social/home': {
			'component': Wall,
			'props': {}
		},
		'social/profile/*': {
			'component': Profile,
			'props': {
				'user_id': frappe.get_route()[2],
				'key': frappe.get_route()[2]
			}
		},
		'social/users': {
			'component': UserList,
			'props': {}
		},
		'not_found': {
			'component': NotFound,
		}
	}
}

export default {
	components: {
		ImageViewer
	},
	data() {
		return {
			current_page: this.get_current_page(),
			show_preview: false,
			preview_image_src: ''
		}
	},
	created() {
		this.$root.$on('show_preview', (src) => {
			this.preview_image_src = src;
			this.show_preview = true;
		})

		this.$root.$on('hide_preview', () => {
			this.preview_image_src = '';
			this.show_preview = false;
		})

		this.update_primary_action(frappe.get_route()[1])
	},
	mounted() {
		frappe.route.on('change', () => {
			if (frappe.get_route()[0] === 'social') {
				this.set_current_page();
				this.update_primary_action(frappe.get_route()[1])
				frappe.utils.scroll_to(0);
				$("body").attr("data-route", frappe.get_route_str());
			}
		});
		frappe.ui.setup_like_popover($(this.$refs.social), '.likes', false);
	},
	methods: {
		set_current_page() {
			this.current_page = this.get_current_page();
		},
		update_primary_action(current_route) {
			if (current_route === 'home') {
				this.$root.page.set_title(__('Social'));
				frappe.breadcrumbs.update();
				this.$root.page.set_primary_action(__('Post'), () => {
					frappe.social.post_dialog.show();
				});
			} else {
				frappe.breadcrumbs.add({
					type: 'Custom',
					label: __('Social Home'),
					route: '#social/home'
				});
				this.$root.page.clear_primary_action();
			}

			if (current_route === 'users') {
				this.$root.page.set_title(__('Leaderboard'));
			}
		},
		get_current_page() {
			const route_map = get_route_map();
			const route = frappe.get_route_str();
			if (route_map[route]) {
				return route_map[route];
			} else {
				return route_map[route.substring(0, route.lastIndexOf('/')) + '/*'] || route_map['not_found']
			}
		},
	}
}
</script>
