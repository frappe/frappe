<template>
	<!--
    frappe-ui POC island.

    Shadow-DOM / mount / portal / router / theme plumbing lives in
    `mountVueIsland` (frappe/public/js/frappe/ui/vue_island.js). The island
    mounts inside a shadow root, so this component owns the full canvas.

    frappe-ui components are imported from the `frappe-ui` barrel and compiled
    from source by the Vite islands pipeline (esbuild/build-islands.mjs).
  -->
	<div class="poc-root min-h-full bg-surface-white px-6 py-8">
		<div class="mx-auto max-w-5xl space-y-6">
			<!-- Hero -->
			<header
				class="rounded-2xl border border-outline-gray-1 bg-surface-white p-6 shadow-sm"
			>
				<div class="flex items-start gap-4">
					<div
						class="grid size-11 shrink-0 place-items-center rounded-xl bg-surface-gray-2 text-ink-gray-8"
					>
						<LucideSparkles class="size-6" />
					</div>
					<div class="min-w-0">
						<h1 class="text-2xl font-semibold text-ink-gray-9">frappe-ui in Desk</h1>
						<p class="mt-1 max-w-2xl text-p-base text-ink-gray-6">
							A live gallery of <strong>frappe-ui</strong> components rendered inside
							a classic Frappe Desk page — mounted as a lazy-loaded Vue 3 island,
							fully style-isolated in a Shadow DOM.
						</p>
						<div class="mt-3 flex flex-wrap gap-2">
							<Badge theme="blue" variant="subtle" label="Vue 3 island" />
							<Badge theme="green" variant="subtle" label="Shadow DOM" />
							<Badge
								theme="gray"
								variant="subtle"
								label='import { … } from "frappe-ui"'
							/>
						</div>
					</div>
				</div>
			</header>

			<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
				<!-- Buttons -->
				<section :class="cardClass">
					<div :class="cardHeadClass">
						<h2 :class="cardTitleClass">Buttons</h2>
						<p :class="cardSubClass">Variants, themes, sizes, icons & states.</p>
					</div>
					<div class="space-y-4">
						<div class="flex flex-wrap items-center gap-2">
							<Button variant="solid">Solid</Button>
							<Button variant="subtle">Subtle</Button>
							<Button variant="outline">Outline</Button>
							<Button variant="ghost">Ghost</Button>
						</div>
						<div class="flex flex-wrap items-center gap-2">
							<Button variant="solid" theme="gray">Gray</Button>
							<Button variant="solid" theme="blue">Blue</Button>
							<Button variant="solid" theme="green">Green</Button>
							<Button variant="solid" theme="red">Red</Button>
						</div>
						<div class="flex flex-wrap items-center gap-2">
							<Button :icon-left="LucidePlus" variant="subtle">New</Button>
							<Button :icon-right="LucideRocket" variant="outline">Deploy</Button>
							<Button :icon="LucideSettings" variant="ghost" />
							<Button
								variant="solid"
								theme="blue"
								:loading="saving"
								@click="simulateSave"
							>
								{{ saving ? "Saving…" : "Save" }}
							</Button>
						</div>
					</div>
				</section>

				<!-- Form controls -->
				<section :class="cardClass">
					<div :class="cardHeadClass">
						<h2 :class="cardTitleClass">Form controls</h2>
						<p :class="cardSubClass">Two-way bound — edit and watch the summary.</p>
					</div>
					<div class="space-y-3">
						<FormControl
							v-model="form.name"
							type="text"
							label="Project name"
							placeholder="e.g. Helpdesk revamp"
						/>
						<Select v-model="form.team" :options="teamOptions" label="Team" />
						<Combobox
							v-model="form.repo"
							:options="repos"
							label="Repository"
							placeholder="Search a repo…"
							open-on-focus
						/>
						<div class="flex items-center gap-5 pt-1">
							<Switch v-model="form.notify" label="Notifications" />
							<Checkbox v-model="form.terms" label="Accept terms" />
						</div>
					</div>
					<div
						class="mt-4 rounded-lg border border-outline-gray-1 bg-surface-gray-2 p-3"
					>
						<p class="text-p-sm text-ink-gray-7">
							<span class="text-ink-gray-5">Summary —</span>
							<strong>{{ form.name || "Untitled" }}</strong> for
							<strong>{{ teamLabel }}</strong
							>, repo <strong>{{ form.repo || "—" }}</strong
							>, notifications <strong>{{ form.notify ? "on" : "off" }}</strong
							>, terms <strong>{{ form.terms ? "accepted" : "pending" }}</strong
							>.
						</p>
					</div>
				</section>

				<!-- Overlays -->
				<section :class="cardClass">
					<div :class="cardHeadClass">
						<h2 :class="cardTitleClass">Overlays</h2>
						<p :class="cardSubClass">
							Dialogs, popovers & tooltips — teleported into the shadow root.
						</p>
					</div>
					<div class="flex flex-wrap items-center gap-2">
						<Button variant="solid" @click="basicDialogOpen = true"
							>Basic dialog</Button
						>
						<Button variant="subtle" @click="formDialogOpen = true"
							>Form dialog</Button
						>
						<Button variant="subtle" theme="red" @click="confirmDialogOpen = true">
							Confirm dialog
						</Button>

						<Popover>
							<template #target="{ togglePopover }">
								<Button
									variant="outline"
									:icon-left="LucideBell"
									@click="togglePopover()"
								>
									Popover
								</Button>
							</template>
							<template #body-main>
								<div class="w-64 p-4">
									<p class="mb-1 text-p-base font-medium text-ink-gray-8">
										Portaled content
									</p>
									<p class="text-p-sm text-ink-gray-6">
										Teleported via reka-ui's <code>PopoverPortal</code> into
										the island's in-shadow target — styled and isolated from
										Desk.
									</p>
								</div>
							</template>
						</Popover>

						<Tooltip text="I'm a frappe-ui tooltip, inside the shadow root.">
							<Button variant="ghost" :icon="LucideInfo" />
						</Tooltip>
					</div>

					<div
						v-if="lastSubmit || confirmResult"
						class="mt-4 rounded-lg border border-outline-gray-1 bg-surface-gray-2 p-3 text-p-sm text-ink-gray-7"
					>
						<p v-if="lastSubmit">
							Form dialog submitted: <strong>{{ lastSubmit }}</strong>
						</p>
						<p v-if="confirmResult">
							Confirm dialog: <strong>{{ confirmResult }}</strong>
						</p>
					</div>
				</section>

				<!-- Display -->
				<section :class="cardClass">
					<div :class="cardHeadClass">
						<h2 :class="cardTitleClass">Display</h2>
						<p :class="cardSubClass">Badges & avatars with frappe-ui design tokens.</p>
					</div>
					<div class="space-y-4">
						<div class="flex flex-wrap items-center gap-2">
							<Badge theme="gray" label="Backlog" />
							<Badge theme="blue" label="In progress" />
							<Badge theme="orange" label="Review" />
							<Badge theme="green" label="Done" />
							<Badge theme="red" variant="outline" label="Blocked" />
						</div>
						<div class="flex flex-wrap items-center gap-2">
							<Badge theme="green" variant="solid" label="Solid" />
							<Badge theme="green" variant="subtle" label="Subtle" />
							<Badge theme="green" variant="outline" label="Outline" />
							<Badge theme="green" variant="ghost" label="Ghost" />
						</div>
						<div class="flex items-center gap-2 pt-1">
							<Avatar label="Frappe" />
							<Avatar label="ERPNext" />
							<Avatar label="CRM" shape="square" />
							<Avatar label="HD" size="lg" />
						</div>
					</div>
				</section>
			</div>

			<!-- Footer note -->
			<p class="px-1 text-center text-p-sm text-ink-gray-5">
				Same Vue 3 runtime as Form Builder & Workflow Builder · styles scoped by a Shadow
				DOM · unused components tree-shaken out of the island bundle.
			</p>
		</div>

		<!-- Basic dialog -->
		<Dialog v-model="basicDialogOpen" :options="{ title: 'Hello from frappe-ui' }">
			<template #body-content>
				<p class="text-p-base text-ink-gray-7">
					This dialog is a <strong>frappe-ui</strong> component compiled from source by
					the Vite islands pipeline and rendered inside a Bootstrap-era Desk page.
				</p>
				<p class="mt-3 text-p-sm text-ink-gray-5">
					Its overlay is teleported into the island's shadow root, so the Tailwind
					preflight and design tokens stay fully isolated from Desk's global CSS.
				</p>
			</template>
			<template #actions>
				<Button variant="solid" @click="basicDialogOpen = false">Got it</Button>
			</template>
		</Dialog>

		<!-- Form dialog -->
		<Dialog
			v-model="formDialogOpen"
			:options="{
				title: 'Create project',
				size: 'md',
				actions: [
					{ label: 'Create', variant: 'solid', onClick: handleSubmit },
					{ label: 'Cancel', onClick: ({ close }) => close() },
				],
			}"
		>
			<template #body-content>
				<div class="space-y-4">
					<FormControl
						v-model="dialogForm.name"
						type="text"
						label="Name"
						placeholder="Project name…"
					/>
					<FormControl
						v-model="dialogForm.description"
						type="textarea"
						label="Description"
						placeholder="What is this about?"
					/>
				</div>
			</template>
		</Dialog>

		<!-- Confirm dialog -->
		<Dialog
			v-model="confirmDialogOpen"
			:options="{
				title: 'Delete project',
				message: 'This will permanently delete the project. This action cannot be undone.',
				icon: { name: 'alert-triangle', theme: 'red' },
				actions: [
					{
						label: 'Delete',
						variant: 'solid',
						theme: 'red',
						onClick: ({ close }) => {
							confirmResult = 'Deleted';
							close();
						},
					},
					{
						label: 'Cancel',
						onClick: ({ close }) => {
							confirmResult = 'Cancelled';
							close();
						},
					},
				],
			}"
		/>
	</div>
</template>

<script setup lang="ts">
import {
	Button,
	Badge,
	Avatar,
	Switch,
	Checkbox,
	FormControl,
	Select,
	Combobox,
	Popover,
	Tooltip,
	Dialog,
} from "frappe-ui";
import { computed, reactive, ref } from "vue";
import LucideSparkles from "~icons/lucide/sparkles";
import LucidePlus from "~icons/lucide/plus";
import LucideRocket from "~icons/lucide/rocket";
import LucideSettings from "~icons/lucide/settings";
import LucideBell from "~icons/lucide/bell";
import LucideInfo from "~icons/lucide/info";

// Shared card styling (frappe-ui design tokens).
const cardClass = "rounded-2xl border border-outline-gray-1 bg-surface-white p-5 shadow-sm";
const cardHeadClass = "mb-4";
const cardTitleClass = "text-lg font-semibold text-ink-gray-8";
const cardSubClass = "mt-0.5 text-p-sm text-ink-gray-5";

const saving = ref(false);
function simulateSave() {
	saving.value = true;
	setTimeout(() => (saving.value = false), 1200);
}

const teamOptions = [
	{ label: "Engineering", value: "engineering" },
	{ label: "Design", value: "design" },
	{ label: "Support", value: "support" },
];
const repos = [
	"frappe",
	"frappe-ui",
	"erpnext",
	"helpdesk",
	"crm",
	"insights",
	"gameplan",
	"builder",
];

const form = reactive({
	name: "",
	team: "engineering",
	repo: "frappe-ui",
	notify: true,
	terms: false,
});
const teamLabel = computed(() => teamOptions.find((t) => t.value === form.team)?.label ?? "—");

const basicDialogOpen = ref(false);
const formDialogOpen = ref(false);
const confirmDialogOpen = ref(false);

const dialogForm = reactive({ name: "", description: "" });
const lastSubmit = ref("");
const confirmResult = ref("");

function handleSubmit({ close }: { close: () => void }) {
	lastSubmit.value = dialogForm.name
		? `"${dialogForm.name}"${dialogForm.description ? " — " + dialogForm.description : ""}`
		: "(empty)";
	close();
}
</script>
