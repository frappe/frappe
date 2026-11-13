// What the rule popover edits: a draft of one stored rule, in Rules (a builder tree) or Code (the text
// as written). The row stages the draft once, when the popover closes, so a session is one undo step.
import { computed, ref, shallowRef } from "vue";
import { emptyTree } from "@framework/ui/ConditionBuilder";
import type { RuleTree } from "./ruleWords";

export type RuleMode = "rules" | "code";

/** Reads and writes one kind of stored rule: a condition or a Link's filters. */
export interface RuleCodec {
	/** null when the builder cannot show the text unchanged. */
	read(raw: string): RuleTree | null;
	write(tree: RuleTree): string;
	/** The text the Code tab shows for a stored value. */
	code(raw: string): string;
	/** The stored value for what the Code tab holds, shown from the stored value `shownFrom`. */
	fromCode(text: string, shownFrom: string): string;
	/** Why the tree cannot be stored; "" when it can. */
	problem?(tree: RuleTree): string;
}

export class RuleDraft {
	readonly value = ref("");
	readonly tree = shallowRef<RuleTree>(emptyTree());
	readonly code = ref("");
	readonly mode = ref<RuleMode>("rules");
	readonly readable = computed(() => this.codec.read(this.value.value) !== null);
	readonly problem = computed(() => this.codec.problem?.(this.tree.value) ?? "");
	private codeShownFrom: string;

	constructor(
		readonly original: string,
		private codec: RuleCodec,
	) {
		this.value.value = original;
		const tree = codec.read(original);
		this.tree.value = tree ?? emptyTree();
		this.mode.value = tree ? "rules" : "code";
		this.code.value = codec.code(original);
		this.codeShownFrom = original;
	}

	changed(): boolean {
		return this.value.value !== this.original;
	}

	setTree(tree: RuleTree | null) {
		this.tree.value = tree ?? emptyTree();
		// A tree with a problem is not staged: the value stays the last one without.
		if (!this.problem.value) this.value.value = this.codec.write(this.tree.value);
	}

	setCode(text: string) {
		this.code.value = text;
		this.value.value = this.codec.fromCode(text, this.codeShownFrom);
	}

	/** Rules only while the builder can read the draft. */
	switchTo(mode: RuleMode) {
		if (mode === "rules") {
			const tree = this.codec.read(this.value.value);
			if (!tree) return;
			this.tree.value = tree;
		} else {
			this.code.value = this.codec.code(this.value.value);
			this.codeShownFrom = this.value.value;
		}
		this.mode.value = mode;
	}

	clear() {
		this.tree.value = emptyTree();
		this.code.value = "";
		this.codeShownFrom = "";
		this.mode.value = "rules";
		this.value.value = "";
	}
}
