<template>
	<div class="post-skeleton flex-column justify-between">
		<div class="post-skeleton-body">
			<div class="flex">
				<div class="avatar avatar-medium"></div>
				<div class="user-name"></div>
			</div>
			<div class="content"></div>
		</div>
		<div class="post-skeleton-foot"></div>
	</div>
</template>
<style lang="less" scoped>
@base-color: #f8f8f8;
@shine-color: #fcfcfc;
@animation-duration: 3s;

@keyframes load {
	0% {
		background-position: -100px
	}

	40%, 100% {
		background-position: 500px
	}
}

.background-img() {
	background-image: linear-gradient(90deg, @base-color 0px, @shine-color 40px, @base-color 80px);
	background-size: 600px
}
.post-skeleton {
	height: 250px;
	border-radius: 4px;
	max-width: 600px;
	border: 1px solid #ededed;
	margin-bottom: 15px;
	.post-skeleton-body {
		padding: 15px;
		.user-name {
			height: 10px;
			width: 100px;
			margin-left: 5px;
		}
		.content {
			height: 100px;
			margin: 15px 0 0 46px;
		}
		.user-name, .avatar, .content {
			.background-img();
			border-radius: 4px;
			animation: load @animation-duration infinite linear;
		}
	}
	.post-skeleton-foot {
		width: 100%;
		height: 40px;
		background: @base-color;
	}
}
</style>