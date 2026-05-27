import logging

import frappe
import litellm
from frappe import _

from studio.ai_block_codec import BlockCodec
from studio.ai_models import ModelRegistry

litellm.drop_params = True
logger = frappe.logger("studio.ai")
logger.setLevel(logging.INFO)

TASK_PARAMS = {
	"simple": {"max_tokens": 1000, "temperature": 0.5},
	"complex": {"max_tokens": 40000, "temperature": 0.7},
}

COMPONENT_CATALOG = """
LAYOUT:
- container: layout wrapper (renders as a div). No componentProps. Use baseStyles: display, flexDirection, gap, padding, width, height, flexWrap, alignItems, justifyContent, flexShrink, flex, etc.

TEXT & DISPLAY:
- TextBlock: {text: "string", tag: "p|h1|h2|h3|h4|h5|h6|span"}
- Badge: {variant: "subtle|solid|outline", theme: "green|red|orange|blue|gray", size: "sm|md|lg", label: "string"}
- Avatar: {shape: "circle|square", size: "xs|sm|md|lg|xl|2xl|3xl", label: "initials", image: "url"}
- Progress: {value: 0-100, size: "sm|md|lg", label: "string"}
- Alert: {title: "string", description: "string", theme: "yellow|red|green|blue"}
- ErrorMessage: {message: "string"}
- FeatherIcon: {name: "feather-icon-name", class: "h-5 w-5"}
- ImageView: {image: "url", size: "xs|sm|md|lg|xl"}
- Divider: (no props)
- Tooltip: {text: "string"}
- HTML: {html: "<p>raw html</p>"}

INPUTS:
- TextInput: {placeholder: "string"}
- Textarea: {placeholder: "string"}
- FormControl: {type: "text|email|number|select|date|autocomplete|password", label: "string", placeholder: "string"}
- Select: {placeholder: "string", options: [{label: "string", value: "string"}]}
- Checkbox: {label: "string", checked: true|false}
- Switch: {label: "string", description: "string", modelValue: true|false}
- DatePicker: {placeholder: "string"}
- TimePicker: {placeholder: "string"}
- DateTimePicker: {placeholder: "string"}
- MultiSelect: {placeholder: "string", options: [{label: "string", value: "string"}]}
- Rating: {label: "string"}
- FileUploader: {label: "string", fileTypes: "['image/*']"}
- TextEditor: {modelValue: "string", editable: true, fixedMenu: true}

ACTIONS:
- Button: {label: "string", variant: "solid|subtle|outline|ghost", size: "sm|md|lg|xl|2xl", theme: "gray (DEFAULT — omit unless red/green/blue is semantically required)"}
- Dropdown: {options: [{label: "string", icon: "feather-icon"}], button: {label: "string"}}

NAVIGATION:
- Breadcrumbs: {items: [{label: "string", route: "string"}]}
- Tabs: {tabs: [{label: "string"}]}
- TabButtons: {buttons: [{label: "string", value: "string"}]}
- Sidebar: {header: {title: "string", subtitle: "string"}, sections: [{label: "string", items: [{label: "string", icon: "string", to: "string"}]}]}

DATA DISPLAY:
- ListView: {columns: [{label: "string", key: "string", width: number}], rows: [{key: value}], rowKey: "string"}
- NumberChart: {config: {title: "string", value: number, prefix: "string", delta: number}}
- AxisChart: {config: {data: [{xKey: val, yKey: val}], xAxis: {key: "string", type: "time|category"}, yAxis: {title: "string"}, series: [{name: "string", type: "bar|line"}]}}
- DonutChart: {config: {data: [{cat: val, val: number}], categoryColumn: "string", valueColumn: "string"}}
- Filter: {doctype: "string", filters: {}}
- Link: {doctype: "string"}
- Tree: {nodeKey: "string", node: {name: "string", label: "string", children: []}}
- Repeater: (no props — repeats child template over data)
- Calendar: {config: {defaultMode: "Month"}, events: []}

AUTOCOMPLETE:
- Autocomplete: {placeholder: "string", options: [{label: "string", value: "string"}]}
- Combobox: {placeholder: "string", options: [{group: "string", options: [{label, value}]}]}
"""

SYSTEM_PROMPT = f"""You are an expert UI builder for Frappe Studio, a Vue.js-based low-code app builder. Your task is to generate a compact YAML block tree that Studio will render as a live Vue application. Each block in the tree maps to a Vue component or native html element (div) or a Studio Vue component or a Frappe UI Vue component.

OUTPUT FORMAT:
Return ONLY valid compact YAML. No markdown fences, no explanations, no JSON.

BLOCK SCHEMA:
name: componentName          # required — must match catalog exactly
originalElement: div|body    # required for container and root blocks
label: descriptive name
props:                        # component-specific props (flow style preferred)
  key: value
style:                        # CSS-in-JS camelCase (flow style preferred)
  key: value
mstyle:                       # mobile style overrides
  key: value
tstyle:                       # tablet style overrides
  key: value
slots:                        # componentSlots for frappe-ui components that hold child content
  slotName: ...
c:                            # children list
- name: ...

ROOT BLOCK:
Always start with:
name: div
originalElement: body
label: body
style: {{display: flex, flexDirection: column, flexShrink: 0, width: inherit, overflowX: hidden, height: 100%}}
c:
- ...

LAYOUT CONTAINERS (CRITICAL — originalElement is required or children won't render):
name: container
originalElement: div
label: container
style: {{display: flex, flexDirection: row|column, gap: ..., padding: ...}}
c:
- ...
- Use container for all inner layout wrappers — never use "div" as name for inner blocks
- flexDirection: row for horizontal layouts, column for vertical
- Use gap, padding for spacing. width: 100% for full-width sections. flex: 1 to fill space.

COMPONENT STYLING RULES:
- Always use CSS variables. Avoid raw hex colors/values.
	- backgroundColor:  var(--surface-white) | var(--surface-gray-1..7) | var(--surface-cards) | var(--surface-red-1) | var(--surface-green-1) | var(--surface-amber-1) | var(--surface-blue-1)
	- color (text): var(--ink-white) | var(--ink-gray-1..9)
	- borderColor: var(--outline-white) | var(--outline-gray-1..5) | var(--outline-red-1..3) | var(--outline-green-1..2) | var(--outline-amber-1..2) | var(--outline-blue-1) | var(--outline-orange-1)
	- borderWidth
	- borderStyle: solid | dashed | dotted
	- NEVER use the `border` shorthand — always set borderColor, borderWidth, borderStyle as separate keys
	- boxShadow: "sm" | "DEFAULT" | "md" | "lg" | "xl" | "2xl" | "none" (keywords only, not raw values)
	- borderRadius: "none" (0px) | "sm" (0.25rem) | "DEFAULT" (0.5rem) | "md" (0.625rem) | "lg" (0.75rem) | "xl" (1rem) | "2xl" (1.25rem) | "full" (9999px)
- Button: use size prop ("sm"|"md"|"lg"|"xl"|"2xl") for sizing — DO NOT set height in style. Keep `theme` gray or default unless prompted. Only use colored themes (blue, red, green) when semantically meaningful: destructive actions → red, success/confirmed → green.
- Avoid applying visual style (color, backgroundColor, borderColor, fontSize) to frappe-ui components (eg: height on Button component) — their props handle this. Only use style on components for layout (width, flex, margin, etc.).
- TextBlock: use tag prop for semantics (h1/h2/h3 for headings, p for body). Set fontSize/fontWeight/color on TextBlock style.

AVAILABLE COMPONENTS:
{COMPONENT_CATALOG}

RULES:
- name must exactly match a component from the catalog above (or "div" for root, "container" for inner wrappers)
- style keys must be camelCase CSS (backgroundColor, borderRadius, fontSize, etc.)
- Do NOT include id (componentId is auto-generated by Studio)
- Do NOT include parentBlock
- Omit keys whose value is null, empty string, empty dict, or empty list
- Keep props to only what's relevant to the description

EXAMPLE — "A login form with email, password and a submit button":
name: div
originalElement: body
label: body
style: {{display: flex, flexDirection: column, flexShrink: 0, width: inherit, overflowX: hidden, height: 100%}}
c:
- name: container
  originalElement: div
  label: page
  style: {{display: flex, flexDirection: column, alignItems: center, justifyContent: center, flex: 1, padding: 24px}}
  c:
  - name: container
    originalElement: div
    label: card
    style: {{display: flex, flexDirection: column, gap: 16px, width: 100%, maxWidth: 400px, padding: 32px, backgroundColor: 'var(--surface-white)', borderRadius: '0.75rem', boxShadow: md}}
    c:
    - name: TextBlock
      props: {{text: Sign In, tag: h2}}
      style: {{fontSize: 20px, fontWeight: '600', color: 'var(--ink-gray-9)'}}
    - name: TextInput
      props: {{placeholder: Email address}}
    - name: FormControl
      props: {{type: password, label: Password, placeholder: Enter password}}
    - name: Button
      props: {{label: Sign In, variant: solid}}
"""


def call_llm(messages: list, model: str, task_tier: str, api_key: str, stream: bool = False):
	params = TASK_PARAMS[task_tier]
	return litellm.completion(model=model, messages=messages, api_key=api_key, stream=stream, **params)


def _emit(event_suffix: str, page_id: str, user: str, **kwargs):
	frappe.publish_realtime(
		f"ai_generation_{event_suffix}_{page_id}",
		{"page_id": page_id, **kwargs},
		user=user,
	)


def _progress_stage(content: str) -> str | None:
	"""Extract a human-readable stage from the tail of a partial YAML stream."""
	lookback = content[-400:]
	for section_type in ("section", "nav", "header", "footer"):
		if lookback.rfind(f"label: {section_type}") != -1 or lookback.rfind(f"name: {section_type}") != -1:
			return f"Building {section_type}…"
	return None


def run_generation_job(prompt: str, model: str, page_id: str, user: str):
	settings = frappe.get_single("Studio Settings")
	api_key = settings.get_password("ai_api_key", raise_exception=False)

	_emit("progress", page_id, user, message=f"Generating with {ModelRegistry.get_label(model)}…")

	content = ""
	try:
		messages = [
			{"role": "system", "content": SYSTEM_PROMPT},
			{"role": "user", "content": f"Create a page for: {prompt}"},
		]
		for chunk in call_llm(messages, model, "complex", api_key, stream=True):
			delta = chunk.choices[0].delta.content
			if not delta:
				continue
			content += delta
			_emit("stream", page_id, user, chunk=delta)
			stage = _progress_stage(content)
			if stage:
				_emit("progress", page_id, user, message=stage)

		logger.info(f"run_generation_job stream done | model={model} length={len(content)}")
		block = BlockCodec.parse_blocks(content)
		_emit("complete", page_id, user, block=block)

	except Exception as e:
		logger.error(f"run_generation_job failed: {e}", exc_info=True)
		frappe.log_error(title="Studio AI: generation error", message=str(e))
		_emit("error", page_id, user, message=str(e))


@frappe.whitelist()
def generate_page_from_prompt(prompt: str, model: str | None, page_id: str) -> dict:
	if not frappe.has_permission("Studio Page", ptype="write"):
		frappe.throw(_("You do not have permission to modify pages"))

	settings = frappe.get_single("Studio Settings")
	if not settings.get_password("ai_api_key", raise_exception=False):
		frappe.throw(_("OpenRouter API key is not configured. Please set it in Studio Settings."))

	resolved_model = model or ModelRegistry.get_default()

	frappe.enqueue(
		run_generation_job,
		queue="long",
		prompt=prompt,
		model=resolved_model,
		page_id=page_id,
		user=frappe.session.user,
	)

	frappe.local.response.http_status_code = 202
	return {"status": "accepted"}
