<template>
	<Dialog
		:model-value="state.open"
		title="Review dependency conflicts"
		size="2xl"
		@update:model-value="(open: boolean) => !open && dismissPasteConflictDialog()"
	>
		<template #default>
			<div class="flex flex-col gap-4">
				<p class="text-p-base text-ink-gray-7">
					The copied items have the same names as items on this page, but different definitions. Choose which
					version to use for each one.
				</p>

				<div class="max-h-[420px] overflow-auto rounded-lg border border-outline-gray-2">
					<List
						class="w-full"
						:columns="['minmax(0, 1fr)', '8rem', 'minmax(16rem, 1.4fr)']"
						:row-height="52"
						divider="full"
					>
						<ListHeader class="sticky top-0 z-10 bg-surface-gray-1">
							<ListHeaderCell class="pl-3">Name</ListHeaderCell>
							<ListHeaderCell>Type</ListHeaderCell>
							<ListHeaderCell class="pr-3">Version</ListHeaderCell>
						</ListHeader>
						<ListRows :items="state.choices" row-key="id" v-slot="{ item: choice }">
							<ListRow>
								<ListCell class="pl-3">
									<span class="truncate text-sm font-medium text-ink-gray-9" :title="choice.name">
										{{ choice.name }}
									</span>
								</ListCell>
								<ListCell>
									<span class="text-sm text-ink-gray-6">{{ typeLabels[choice.kind] }}</span>
								</ListCell>
								<ListCell class="pr-3">
									<TabButtons
										v-model="choice.resolution"
										:options="resolutionOptions"
										:aria-label="`Version to use for ${choice.name}`"
									/>
								</ListCell>
							</ListRow>
						</ListRows>
					</List>
				</div>

				<p v-if="hasComponentConflict" class="text-sm text-ink-gray-6">
					Using a copied component can affect blocks on other pages.
				</p>
				<ErrorMessage v-if="state.error" :message="state.error" />
			</div>
		</template>

		<template #actions>
			<div class="flex w-full items-center justify-end gap-3">
				<Button
					label="Revert pasted blocks"
					theme="red"
					variant="subtle"
					:disabled="state.applying"
					@click="removePastedBlocks"
				/>
				<Button label="Apply" variant="solid" :loading="state.applying" @click="applyPasteConflictChoices" />
			</div>
		</template>
	</Dialog>
</template>

<script lang="ts">
import { reactive } from "vue"

export type PasteConflictKind = "components" | "resources" | "variables"
export type PasteConflictResolution = "existing" | "copied"

export interface PasteConflictChoice {
	id: string
	kind: PasteConflictKind
	name: string
	existing: Record<string, any>
	copied: Record<string, any>
	resolution: PasteConflictResolution
}

interface PasteConflictCallbacks {
	onApply: (choices: PasteConflictChoice[]) => void | Promise<void>
	onDismiss: () => void
	onRemove: () => void
}

const state = reactive({
	open: false,
	applying: false,
	error: "",
	choices: [] as PasteConflictChoice[],
})

let callbacks: PasteConflictCallbacks | undefined

export function showPasteConflictDialog(
	choices: Omit<PasteConflictChoice, "resolution">[],
	nextCallbacks: PasteConflictCallbacks,
) {
	callbacks = nextCallbacks
	state.choices = choices.map((choice) => ({
		...choice,
		resolution: "existing",
	}))
	state.error = ""
	state.open = true
}

async function applyPasteConflictChoices() {
	if (!callbacks || state.applying) return
	state.applying = true
	state.error = ""
	try {
		await callbacks.onApply(state.choices)
		closePasteConflictDialog()
	} catch (error: any) {
		state.error = error?.messages?.[0] || error?.message || "Could not apply the selected versions."
	} finally {
		state.applying = false
	}
}

function dismissPasteConflictDialog() {
	if (!state.open || state.applying) return
	callbacks?.onDismiss()
	closePasteConflictDialog()
}

function removePastedBlocks() {
	if (!state.open || state.applying) return
	callbacks?.onRemove()
	closePasteConflictDialog()
}

function closePasteConflictDialog() {
	state.open = false
	callbacks = undefined
}
</script>

<script setup lang="ts">
import { computed } from "vue"
import { Button, Dialog, ErrorMessage, TabButtons } from "frappe-ui"
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from "frappe-ui/list"

const typeLabels: Record<PasteConflictKind, string> = {
	components: "Component",
	resources: "Data source",
	variables: "Variable",
}

const resolutionOptions = [
	{ label: "Keep existing", value: "existing" },
	{ label: "Use copied", value: "copied" },
]

const hasComponentConflict = computed(() => state.choices.some(({ kind }) => kind === "components"))
</script>
