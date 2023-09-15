export function get_workflow_elements(workflow, workflow_data) {
	let elements = [];
	let states = {};
	let actions = {};
	let x = 150;
	let y = 100;

	function state_obj(id, data) {

		let state = workflow_data.filter(el => el.type == 'state' && el.data.state == data.state)

		if (state.length) {
			state[0].data = data
			if (!states[data.state]) {
				states[data.state] = [state[0].id, state[0].position];
			}
			return state[0]
		}

		state = {
			id: id.toString(),
			type: "state",
			position: { x, y },
			data: data,
		};
		if (!states[data.state]) {
			states[data.state] = [id, { x, y }];
		}
		return state;
	}

	function action_obj(id, data, position) {
		let action = workflow_data.filter(el => el.type == 'action' &&
			el.data.action == data.action && el.data.from == data.from && el.data.to == data.to)

		if (action.length) {
			action[0].data = data
			if (!actions[data.action]) {
				actions[data.action] = [action[0].id, action[0].position]
			}
			return action[0]
		}

		if (!actions[data.action]) {
			actions[data.action] = [id, position]
		}
		return {
			id: "action-" + id,
			type: "action",
			position: position,
			data: data,
		};
	}

	function transition_obj(id, source, target, transition) {

		transition = workflow_data.filter(el => el.type == 'transition'
			&& el.sourceNode.data[transition.source] == transition[transition.source]
			&& el.targetNode.data[transition.target] == transition[transition.target])

		if (transition.length) {
			return transition[0]
		}

		return {
			id: "edge-" + id,
			type: "transition",
			source: source.toString(),
			target: target.toString(),
			sourceHandle: "right",
			targetHandle: "left",
			updatable: true,
			animated: true,
		};
	}

	workflow.states.forEach((state, i) => {
		x += 400;
		let doc_status_map = {
			0: "Draft",
			1: "Submitted",
			2: "Cancelled",
		};
		elements.push(
			state_obj(i + 1, {
				...state,
				doc_status: doc_status_map[state.doc_status],
			})
		);
	});

	workflow.transitions.forEach((transition, i) => {
		let source = states[transition.state];
		let target = states[transition.next_state];
		let position = { x: source[1].x + 250, y: y + 20 };
		let data = {
			...transition,
			from: transition.state,
			to: transition.next_state,
		};

		let action = "action-" + (i + 1);
		elements.push(action_obj(i + 1, data, position));

		if (actions[transition.action]) {
			([action, position] = actions[transition.action]);
		}

		elements.push(transition_obj(source[0] + "-" + action, source[0], action,
			{state: transition.state, source: "state", target: "action", action: transition.action}));
		elements.push(transition_obj(action + "-" + target[0], action, target[0],
			{action: transition.action, source: "action", target:"state", state: transition.next_state}));
	});

	return elements;
}

export function validate_transitions(state, next_state) {
	let message;
	if (state.doc_status == "Cancelled") {
		message = __("Cannot change state of Cancelled Document <b>({0} State)</b>", [
			state.state,
		]);
	}

	if (state.doc_status == "Submitted" && next_state.doc_status == "Draft") {
		message = __(
			"Submitted document cannot be converted back to draft while transitioning from <b>{0} State</b> to <b>{1} State</b>",
			[state.state, next_state.state]
		);
	}

	if (state.doc_status == "Draft" && next_state.doc_status == "Cancelled") {
		message = __(
			"Cannot cancel before submitting while transitioning from <b>{0} State</b> to <b>{1} State</b>",
			[state.state, next_state.state]
		);
	}
	return message;
}
