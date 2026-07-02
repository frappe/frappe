import { inject, onMounted } from "vue";

// Set the SettingsDialog panel header (title + description) for a static tab.
// Returns the panel so callers needing reactive actions can drive it directly.
export function usePanelHeader(title, description) {
	const panel = inject("panel");
	onMounted(() => panel.set_header({ title, description }));
	return panel;
}
