<template>
	<div class="link-item flush-top small"
		:class="{'onboard-spotlight': onboard, 'disabled-link': disabled_dependent}"
		@mouseover="mouseover" @mouseleave="mouseleave"
	>
		<span :class="['indicator', indicator_color]"></span>

		<span v-if="disabled_dependent" class="link-content text-muted">{{ label || __(name) }}</span>
		<a v-else class="link-content" :href="route">{{ label || __(name) }}</a>

		<div v-if="disabled_dependent" v-show="popover_active"
			@mouseover="popover_hover = true" @mouseleave="popover_hover = false"
			class="module-link-popover popover fade top in" role="tooltip"
		>
			<div class="arrow"></div>
			<h3 class="popover-title" style="display: none;"></h3>
			<div class="popover-content">
				<div class="small text-muted">{{ __("You need to create these first: ") }}</div>
				<div class="small">{{ __(incomplete_dependencies.join(", ")) }}</div>
			</div>
		</div>
	</div>
</template>

<script>
export default {
	props: ['label', 'name', 'dependencies', 'incomplete_dependencies', 'onboard', 'count', 'route', 'doctype', 'open_count'],
	data() {
		return {
			hover: false,
			popover_hover: false,
		}
	},
	computed: {
		disabled_dependent() {
			return this.dependencies && this.incomplete_dependencies;
		},

		indicator_color() {
			if(this.open_count) {
				return 'red';
			}
			if(this.onboard) {
				return this.count ? 'blue' : 'orange';
			};
			return 'grey';
		},

		popover_active() {
			return this.popover_hover || this.hover;
		}
	},
	methods: {
		mouseover() {
			$('.module-link-popover').hide();
			this.hover = true;
		},

		mouseleave() {
			setTimeout(() => {
				this.hover = false;
			}, 300);
		}
	}
}
</script>


<style lang="less" scoped>
.link-item {
	position: relative;
	margin: 10px 0px;
	cursor: default;
}

.onboard-spotlight {
	.link-content {
		font-weight: 600;
	}
}

a:hover, a:focus {
	text-decoration: underline;
}

// Overriding indicator styles
.indicator {
	margin-right: 5px;
	color: inherit;
	font-weight: inherit;
}

.link-content {
	flex: 1;
}

.popover {
	display: block;
	top: -60px;
	max-width: 220px;
}

.popover.top > .arrow {
	left: 20%;
}
</style>
