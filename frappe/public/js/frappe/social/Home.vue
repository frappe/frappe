<template>
	<div ref="social" class="social">
		<component :is="current_page"></component>
		<image-viewer :src="preview_image_src" v-if="show_preview"></image-viewer>
	</div>
</template>

<script>

import Wall from './pages/Wall.vue';
import Profile from './pages/Profile.vue';
import NotFound from './components/NotFound.vue';
import ImageViewer from './components/ImageViewer.vue';

function get_route_map() {
	return {
		'social/home': Wall,
		'social/profile': Profile
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

		frappe.app_updates.on('user_image_updated', () => {
			this.$root.$emit('user_image_updated')
		})
	},
	mounted() {
		frappe.route.on('change', () => {
			if (frappe.get_route()[0] === 'social') {
				this.set_current_page();
				frappe.utils.scroll_to(0);
			}
		});
		frappe.ui.setup_like_popover($(this.$refs.social), '.likes', false);
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
			} else {
				return route_map[route.substring(0, route.lastIndexOf('/'))] || NotFound
			}
		},
	}
}
</script>
