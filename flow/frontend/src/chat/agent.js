import { computed, inject } from "vue";

// The agent in force: a session keeps the one it was created with; otherwise the one a
// new chat starts with.
export function useAgent() {
	const flow = inject("flow");
	const page = inject("flowPage");
	const locked = computed(() => !!flow.state.sessionId);
	const current = computed(() =>
		locked.value
			? flow.state.session?.agent ??
			  flow.state.sessions.find((session) => session.session_id === flow.state.sessionId)
					?.agent
			: page.state.agent
	);
	const title = computed(
		() =>
			page.state.boot.agents.find((agent) => agent.name === current.value)?.title ??
			current.value ??
			"Choose an agent"
	);
	return { locked, current, title };
}
