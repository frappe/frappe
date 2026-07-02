<template>
	<div>
		<div>
			<div class="cloud-settings-advanced-row">
				<div>
					<h3>{{ __("Open your server") }}</h3>
					<p>
						{{
							__(
								"Deploys, scaling, SSH, backups, and adding or changing sites — the full controls live on your server."
							)
						}}
					</p>
				</div>
				<button
					class="btn btn-sm btn-default"
					:disabled="!context.server_url"
					@click="open(context.server_url)"
				>
					{{ __("Open server") }}
					<svg class="icon icon-xs"><use href="#icon-arrow-up-right"></use></svg>
				</button>
			</div>

			<div class="cloud-settings-advanced-row">
				<div>
					<h3>{{ __("Account & billing") }}</h3>
					<p>
						{{
							__(
								"Payment methods, invoices, billing email and your account settings — manage it all in one place."
							)
						}}
					</p>
				</div>
				<button
					class="btn btn-sm btn-default"
					:disabled="!context.account_url"
					@click="open(context.account_url)"
				>
					{{ __("Manage account") }}
					<svg class="icon icon-xs"><use href="#icon-arrow-up-right"></use></svg>
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue";
import { usePanelHeader } from "../panel";

const store = inject("store");
usePanelHeader(__("Advanced"), __("Deeper controls for your server."));
const context = computed(() => store.state.context);

function open(url) {
	if (url) window.open(url, "_blank", "noopener");
}
</script>
