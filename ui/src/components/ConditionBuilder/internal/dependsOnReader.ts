// The grammar of the JavaScript a `depends_on` condition is read in: `||` over
// `&&` over `!`, parentheses, comparisons, and the list and text calls people
// write. A parenthesised group stays a group, so a written tree reads back as
// the same tree.
import type { ConditionNode, DependsOnScope } from "../types";
import { DependsOnRules, type Operand } from "./dependsOnRules";
import { tokenize, type Token } from "./jsTokens";

const COMPARISONS = ["===", "!==", "==", "!=", "<=", ">=", "<", ">"];

export class DependsOnReader {
  private tokens: Token[];
  private at = 0;
  private rules: DependsOnRules;

  constructor(source: string, scope: DependsOnScope) {
    this.tokens = tokenize(source);
    this.rules = new DependsOnRules(scope);
  }

  /** The bare-fieldname form: `is_pos` is `doc.is_pos`, `items` asks for rows. */
  static field(fieldname: string, scope: DependsOnScope): ConditionNode {
    const operand = {
      kind: "field",
      name: fieldname,
      length: scope.tables.has(fieldname),
    };
    return new DependsOnRules(scope).truthy(operand as Operand);
  }

  read(): ConditionNode {
    const node = this.or();
    if (this.isPunct(";")) this.at++;
    if (this.at < this.tokens.length)
      throw new SyntaxError("Unexpected code after the condition");
    return node;
  }

  private or(): ConditionNode {
    return this.chain("||", "or", () => this.and());
  }

  private and(): ConditionNode {
    return this.chain("&&", "and", () => this.unary(false));
  }

  private chain(
    op: string,
    conjunction: "and" | "or",
    next: () => ConditionNode
  ) {
    const conditions = [next()];
    while (this.isPunct(op)) {
      this.at++;
      conditions.push(next());
    }
    return conditions.length === 1
      ? conditions[0]
      : { conjunction, conditions };
  }

  private unary(negated: boolean): ConditionNode {
    if (!this.isPunct("!")) return this.primary(negated);
    this.at++;
    return this.rules.negate(this.unary(true));
  }

  /** `negated`: `!a === b` is `(!a) === b`, a comparison of a boolean, so it stays code. */
  private primary(negated: boolean): ConditionNode {
    if (this.isPunct("("))
      return this.attempt(() => this.orEmpty()) ?? this.parenthesised();
    const between = negated ? null : this.attempt(() => this.between());
    if (between) return between;

    const left = this.operand();
    const op = this.peek();
    if (op?.kind !== "punct" || !COMPARISONS.includes(op.text))
      return this.rules.truthy(left);
    if (negated) throw new SyntaxError("Parenthesise a negated comparison");
    this.at++;
    return this.rules.compare(left, op.text, this.operand());
  }

  private parenthesised(): ConditionNode {
    this.expect("(");
    const inner = this.or();
    this.expect(")");
    return inner;
  }

  /** `(doc.x || "").includes("y")`: contains, safe on an empty field. */
  private orEmpty(): ConditionNode {
    this.expect("(");
    const field = this.operand();
    this.expect("||");
    this.expectEmptyText();
    this.expect(")");
    return this.rules.contains(field, this.includesText());
  }

  /** `"a" <= doc.x && doc.x <= "b"`, the form `between` is written in. */
  private between(): ConditionNode {
    const from = this.literal();
    this.expect("<=");
    const field = this.operand();
    this.expect("&&");
    const again = this.operand();
    this.expect("<=");
    const to = this.literal();
    if (
      field.kind !== "field" ||
      again.kind !== "field" ||
      field.name !== again.name
    ) {
      throw new SyntaxError("Not a range");
    }
    return this.rules.between(field.name, from, to);
  }

  private operand(): Operand {
    const token = this.next();
    if (
      token.kind === "name" &&
      (token.text === "doc" || token.text === "parent")
    ) {
      return this.fieldOperand(token.text);
    }
    if (token.kind === "name" && token.text === "in_list") return this.inList();
    if (token.kind === "name" && token.text === "String")
      return this.stringOf();
    if (token.kind === "punct" && token.text === "[") {
      this.at--;
      return this.listOperand();
    }
    this.at--;
    return { kind: "literal", value: this.literal() };
  }

  /** `doc.x`, `parent.x`, `doc.items.length`, `doc.x.includes("y")`. */
  private fieldOperand(object: string): Operand {
    this.expect(".");
    const name = this.next();
    if (name.kind !== "name") throw new SyntaxError("Expected a fieldname");
    const field: Operand = {
      kind: "field",
      name: object === "parent" ? `parent.${name.text}` : name.text,
      length: false,
    };
    if (this.isMember("length")) {
      this.at += 2;
      return { ...field, length: true };
    }
    if (this.isMember("includes"))
      return {
        kind: "row",
        leaf: this.rules.contains(field, this.includesText()),
      };
    return field;
  }

  /** `in_list(["a", "b"], doc.x)`, Frappe's global for a membership. */
  private inList(): Operand {
    this.expect("(");
    const items = this.list();
    this.expect(",");
    const field = this.operand();
    this.expect(")");
    return { kind: "row", leaf: this.rules.member(items, field) };
  }

  /** `String(doc.x ?? "").includes("y")`: contains, safe on a number too. */
  private stringOf(): Operand {
    this.expect("(");
    const field = this.operand();
    this.expect("??");
    this.expectEmptyText();
    this.expect(")");
    return {
      kind: "row",
      leaf: this.rules.contains(field, this.includesText()),
    };
  }

  /** `[...].includes(doc.x)`, or `[...].indexOf(doc.x)` for a comparison with -1. */
  private listOperand(): Operand {
    const items = this.list();
    const method = this.isMember("includes")
      ? "includes"
      : this.isMember("indexOf")
      ? "indexOf"
      : null;
    if (!method) throw new SyntaxError("A list is not a condition");
    this.at += 2;
    this.expect("(");
    const field = this.operand();
    this.expect(")");
    if (method === "includes")
      return { kind: "row", leaf: this.rules.member(items, field) };
    if (field.kind !== "field") throw new SyntaxError("Find a field");
    return { kind: "indexOf", items, name: field.name };
  }

  private list(): (string | number)[] {
    this.expect("[");
    const items: (string | number)[] = [];
    while (!this.isPunct("]")) {
      const item = this.literal();
      if (typeof item !== "string" && typeof item !== "number") {
        throw new SyntaxError("A list holds text and numbers");
      }
      items.push(item);
      if (!this.isPunct("]")) this.expect(",");
    }
    this.expect("]");
    return items;
  }

  private literal(): string | number | boolean | null {
    const token = this.next();
    if (token.kind === "string") return token.text;
    if (token.kind === "number") return Number(token.text);
    if (
      token.kind === "punct" &&
      token.text === "-" &&
      this.peek()?.kind === "number"
    ) {
      return -Number(this.next().text);
    }
    if (
      token.kind === "name" &&
      (token.text === "true" || token.text === "false")
    ) {
      return token.text === "true";
    }
    if (
      token.kind === "name" &&
      (token.text === "null" || token.text === "undefined")
    )
      return null;
    throw new SyntaxError(`Unexpected ${token.text}`);
  }

  /** `.includes("y")` after a field. */
  private includesText(): string {
    this.expect(".");
    const method = this.next();
    if (method.text !== "includes") throw new SyntaxError("Expected includes");
    this.expect("(");
    const text = this.next();
    this.expect(")");
    if (text.kind !== "string") throw new SyntaxError("includes takes text");
    return text.text;
  }

  private expectEmptyText() {
    const token = this.next();
    if (token.kind !== "string" || token.text !== "")
      throw new SyntaxError('Expected ""');
  }

  /** Runs `read`, and rewinds when it throws, for the forms that share a start. */
  private attempt(read: () => ConditionNode): ConditionNode | null {
    const start = this.at;
    try {
      return read();
    } catch {
      this.at = start;
      return null;
    }
  }

  private isMember(name: string) {
    return this.isPunct(".") && this.tokens[this.at + 1]?.text === name;
  }

  private isPunct(text: string) {
    const token = this.peek();
    return token?.kind === "punct" && token.text === text;
  }

  private peek(): Token | undefined {
    return this.tokens[this.at];
  }

  private next(): Token {
    const token = this.tokens[this.at++];
    if (!token) throw new SyntaxError("Unexpected end of condition");
    return token;
  }

  private expect(text: string) {
    const token = this.next();
    if (token.kind !== "punct" || token.text !== text)
      throw new SyntaxError(`Expected ${text}`);
  }
}
