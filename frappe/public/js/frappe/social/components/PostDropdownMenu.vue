<template>
	<div class="dropdown">
		<span class="caret cursor-pointer dropdown-toggle" data-toggle="dropdown"></span>
		<ul class="dropdown-menu">
			<li v-for="option in options" :key="option.label">
				<a @click="option.action">{{option.label}}</a>
			</li>
		</ul>
	</div>
</template>
<script>
export default {
	props: ['options'],
}
</script>
<style lang="less" scoped>
.dropdown-menu {
	min-width: 100px;
	left: auto;
	right: 0;
	a {
		padding: 12px;
		font-size: 10px;
	}
}
</style>

