<!--
  The index's notices: cards in the bottom-right corner. Closing a card tucks it into a bell above
  the avatar for this tab; a notice leaves for good only when its action is done.
-->
<template>
	<TransitionGroup
		tag="div"
		class="fixed bottom-3 right-3 z-10 flex w-80 flex-col gap-2"
		:role="cards.length ? 'region' : undefined"
		:aria-label="cards.length ? __('Notices') : undefined"
		enter-from-class="translate-y-2 opacity-0"
		leave-to-class="translate-y-2 opacity-0"
		enter-active-class="transition duration-200"
		leave-active-class="transition duration-150"
		data-index-notices
	>
		<Alert
			v-for="card in cards"
			:key="card.key"
			class="shadow-lg ring-1 ring-outline-gray-1"
			:icon="card.icon"
			:title="card.title"
			:description="card.description"
			:primary-action="card.action"
			dismissible
			:data-notice="card.key"
			@dismiss="tuck(card.key)"
		/>
	</TransitionGroup>

	<!-- `defer`: the shell draws the foot cell after the page. -->
	<Teleport defer to="[data-index-foot-notices]">
		<Transition
			enter-from-class="scale-75 opacity-0"
			leave-to-class="scale-75 opacity-0"
			enter-active-class="transition duration-200"
			leave-active-class="transition duration-150"
		>
			<div v-if="tucked.length" class="mb-3" data-index-bell>
				<SidebarRailItem
					variant="ghost"
					:label="__n('{0} notice', '{0} notices', tucked.length, [tucked.length])"
					@click="untuck"
				>
					<span class="lucide-bell size-4" aria-hidden="true" />
					<span
						class="absolute -right-0.5 -top-0.5 size-2 rounded-full border border-[var(--surface-base)] bg-surface-gray-7"
						aria-hidden="true"
					/>
				</SidebarRailItem>
			</div>
		</Transition>
	</Teleport>

	<WhatsNewDialog
		v-if="whatsNewOpened"
		v-model="readingWhatsNew"
		@failed="whatsNewOpened = false"
	/>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from "vue";
import { Alert, SidebarRailItem, type AlertAction } from "frappe-ui";
import { __, __n } from "@/i18n";
import { tuckedNotices, type IndexNoticeList, type NoticeKey } from "./notices";

const WhatsNewDialog = defineAsyncComponent(() => import("./WhatsNewDialog.vue"));

type Card = {
	key: NoticeKey;
	icon: string;
	title: string;
	description: string;
	action: AlertAction;
};

const props = defineProps<{ notices: IndexNoticeList; user: string }>();

const memory = tuckedNotices(props.user);
const whatsNewOpened = ref(false);
const tuckedKeys = ref<NoticeKey[]>(memory.recall() ?? []);
const readingWhatsNew = ref(false);
const whatsNew = props.notices.whats_new;

const open = computed(() =>
	allCards().filter((card) => card.key !== "whats_new" || !whatsNewOpened.value)
);
const cards = computed(() => open.value.filter((card) => !tuckedKeys.value.includes(card.key)));
const tucked = computed(() => open.value.filter((card) => tuckedKeys.value.includes(card.key)));

function allCards(): Card[] {
	const { setup } = props.notices;
	return [
		setup && {
			key: "setup" as const,
			icon: "lucide-list-checks",
			title: __("Finish setting up this site"),
			description: __(
				"Apps waiting for the setup wizard: {0}. Until it is done, only System Managers see them here.",
				[setup.apps.join(", ")]
			),
			action: {
				label: __("Continue setup"),
				onClick: () => window.location.assign(setup.route),
			},
		},
		whatsNew && {
			key: "whats_new" as const,
			icon: "lucide-sparkles",
			title: __("Updated to a new version"),
			description: whatsNew.map((entry) => `${entry.title} ${entry.version}`).join(", "),
			action: { label: __("See what's new"), onClick: openWhatsNew },
		},
	].filter((card): card is Card => Boolean(card));
}

function tuck(key: NoticeKey) {
	tuckedKeys.value = [...tuckedKeys.value, key];
	memory.remember(tuckedKeys.value);
}

function untuck() {
	tuckedKeys.value = [];
	memory.remember([]);
}

function openWhatsNew() {
	whatsNewOpened.value = true;
	readingWhatsNew.value = true;
}
</script>
