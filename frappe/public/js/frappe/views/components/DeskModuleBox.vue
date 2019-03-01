<template>
	<div :href="type === 'module' ? '#modules/' + module_name : link"
		class="border module-box"
		:draggable="true"
	>
		<div class="flush-top">
			<div class="module-box-content">
				<div class="level">
					<h4 class="h4">
						<span class="indicator" :class="count ? 'red' : (onboard_present ? 'orange' : 'grey')"></span>
						{{ label }}
					</h4>
					<span class="octicon octicon-three-bars text-extra-muted" style="
						font-size: 12px;
					"></span>
				</div>
				<p
					v-if="shortcuts.length"
					class="small text-muted">
						<a
							v-for="shortcut in shortcuts"
							:key="shortcut.name"
							:href="shortcut.link"
							class="btn btn-default btn-xs shortcut-tag" title="toggle Tag"> {{ shortcut.label }}
						</a>
				</p>
			</div>
		</div>
	</div>
</template>

<script>
export default {
	props: ['name', 'label', 'type', 'module_name', 'link', 'count', 'onboard_present', 'shortcuts', 'description'],
	methods: {
		on_dragstart() {
			return 0;
		},
		on_dragend() {
			return 0;
		},
		on_hover() {
			return 1;
		}
	}
}
</script>

<style lang="less" scoped>
.module-box {
	border-radius: 4px;
	padding: 5px 15px;
	padding-top: 3px;
	display: block;
	background-color: #ffffff;
}

.octicon-three-bars:hover {
	cursor: pointer;
}

.module-box-content {
	width: 100%;

	h4 {
		margin-bottom: 5px
	}

	p {
		margin-top: 5px;
		font-size: 80%;
		display: flex;
		overflow: hidden;
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

.shortcut-tag {
	margin-right: 5px;
}
</style>

