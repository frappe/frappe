import { reactive } from "vue"

export type DependencyKind = "components" | "resources" | "variables"
export type ConflictResolution = "existing" | "copied"

export interface DependencyConflictChoice {
	id: string
	kind: DependencyKind
	name: string
	existing: Record<string, any>
	copied: Record<string, any>
	resolution: ConflictResolution
}

interface DialogCallbacks {
	onApply: (choices: DependencyConflictChoice[]) => void | Promise<void>
	onDismiss: () => void
	onUndo: () => void
}

export const dependencyConflictDialog = reactive({
	open: false,
	applying: false,
	error: "",
	choices: [] as DependencyConflictChoice[],
})

let callbacks: DialogCallbacks | undefined

export function showDependencyConflictDialog(
	choices: Omit<DependencyConflictChoice, "resolution">[],
	nextCallbacks: DialogCallbacks,
) {
	callbacks = nextCallbacks
	dependencyConflictDialog.choices = choices.map((choice) => ({
		...choice,
		resolution: "existing",
	}))
	dependencyConflictDialog.error = ""
	dependencyConflictDialog.open = true
}

export async function applyDependencyConflictChoices() {
	if (!callbacks || dependencyConflictDialog.applying) return
	dependencyConflictDialog.applying = true
	dependencyConflictDialog.error = ""
	try {
		await callbacks.onApply(dependencyConflictDialog.choices)
		closeDependencyConflictDialog()
	} catch (error: any) {
		dependencyConflictDialog.error =
			error?.messages?.[0] || error?.message || "Could not apply the selected versions."
	} finally {
		dependencyConflictDialog.applying = false
	}
}

export function dismissDependencyConflictDialog() {
	if (!dependencyConflictDialog.open || dependencyConflictDialog.applying) return
	callbacks?.onDismiss()
	closeDependencyConflictDialog()
}

export function undoDependencyConflictPaste() {
	if (!dependencyConflictDialog.open || dependencyConflictDialog.applying) return
	callbacks?.onUndo()
	closeDependencyConflictDialog()
}

function closeDependencyConflictDialog() {
	dependencyConflictDialog.open = false
	callbacks = undefined
}
