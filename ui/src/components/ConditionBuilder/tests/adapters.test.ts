import { describe, expect, it } from "vitest";
import {
  fromFrappeConditions,
  toConditionExpression,
  toFrappeConditions,
} from "../adapters";
import type { ConditionGroup, FieldConditionValue } from "../types";
import type { ConditionField } from "../types";

type Tree = ConditionGroup<FieldConditionValue>;

function leaf(
  fieldname: string,
  operator: FieldConditionValue["operator"],
  value: FieldConditionValue["value"]
): FieldConditionValue {
  return { fieldname, operator, value };
}

/** A group over the nodes given, joined by one operator. Defaults to `and`. */
function group(
  conditions: Tree["conditions"],
  conjunction: Tree["conjunction"] = "and"
): Tree {
  return { conjunction, conditions };
}

describe("toConditionExpression", () => {
  it("is empty for a tree with nothing in it", () => {
    expect(toConditionExpression(group([]))).toBe("");
  });

  it("joins a level with the group's one operator, repeated", () => {
    const tree = group(
      [
        leaf("status", "equals", "Open"),
        leaf("priority", "equals", "High"),
        leaf("agent", "equals", "sam"),
      ],
      "or"
    );

    expect(toConditionExpression(tree)).toBe(
      'status == "Open" or priority == "High" or agent == "sam"'
    );
  });

  it("parenthesises a nested group rather than relying on precedence", () => {
    const tree = group(
      [
        group(
          [
            leaf("status", "equals", "Open"),
            leaf("status", "equals", "Replied"),
          ],
          "or"
        ),
        leaf("priority", "equals", "High"),
      ],
      "and"
    );

    expect(toConditionExpression(tree)).toBe(
      '(status == "Open" or status == "Replied") and priority == "High"'
    );
  });

  it("prefixes fieldnames when the host evaluates against a document", () => {
    const tree = group([leaf("status", "equals", "Open")]);

    expect(toConditionExpression(tree, { fieldPrefix: "doc" })).toBe(
      'doc.status == "Open"'
    );
  });

  describe("operators", () => {
    const compile = (
      operator: FieldConditionValue["operator"],
      value: FieldConditionValue["value"]
    ) => toConditionExpression(group([leaf("subject", operator, value)]));

    it("compiles equality and its aliases", () => {
      expect(compile("equals", "refund")).toBe('subject == "refund"');
      expect(compile("not equals", "refund")).toBe('subject != "refund"');
    });

    it("compiles like to a membership test guarded on the field", () => {
      expect(compile("like", "refund")).toBe(
        '(subject and "refund" in subject)'
      );
      expect(compile("not like", "refund")).toBe(
        '(subject and "refund" not in subject)'
      );
    });

    it("compiles in from a list and from a comma string alike", () => {
      expect(compile("in", ["Open", "Replied"])).toBe(
        '(subject and subject in ["Open", "Replied"])'
      );
      expect(compile("in", "Open, Replied")).toBe(
        '(subject and subject in ["Open", "Replied"])'
      );
      expect(compile("not in", ["Open"])).toBe(
        '(subject and subject not in ["Open"])'
      );
    });

    it("compiles between to two comparisons, from a pair or a comma string", () => {
      expect(compile("between", ["2026-01-01", "2026-01-31"])).toBe(
        '(subject >= "2026-01-01" and subject <= "2026-01-31")'
      );
      expect(compile("between", "2026-01-01,2026-01-31")).toBe(
        '(subject >= "2026-01-01" and subject <= "2026-01-31")'
      );
    });

    it("compiles every set/not set pairing to the field's truthiness", () => {
      expect(compile("is", "set")).toBe("subject");
      expect(compile("is", "not set")).toBe("not subject");
      expect(compile("is not", "set")).toBe("not subject");
      // CRM's compiler leaves this one to fall through to `subject is not "not
      // set"`, which is true of every document.
      expect(compile("is not", "not set")).toBe("subject");
    });

    it("compiles a Check field's Yes/No to the field itself", () => {
      expect(compile("equals", "Yes")).toBe("subject");
      expect(compile("equals", "No")).toBe("not subject");
      expect(compile("not equals", "Yes")).toBe("not subject");
      expect(compile("not equals", "No")).toBe("subject");
    });

    it("compiles an unset value to the field's own falsiness", () => {
      expect(compile("equals", null)).toBe("not subject");
      expect(compile(">", null)).toBe("subject");
    });

    it("emits numbers bare and booleans as Python's", () => {
      expect(compile(">", 5)).toBe("subject > 5");
      expect(compile("equals", true)).toBe("subject == True");
      expect(compile("equals", false)).toBe("subject == False");
    });

    it("escapes a value that would otherwise end the literal early", () => {
      expect(compile("equals", 'a "quoted" word')).toBe(
        'subject == "a \\"quoted\\" word"'
      );
      expect(compile("equals", "back\\slash")).toBe(
        'subject == "back\\\\slash"'
      );
    });
  });

  describe("with the doctype's fields", () => {
    const fields: ConditionField[] = [
      {
        label: "Is Open",
        value: "is_open",
        fieldname: "is_open",
        fieldtype: "Check",
      },
      {
        label: "Subject",
        value: "subject",
        fieldname: "subject",
        fieldtype: "Data",
      },
      {
        label: "Grand Total",
        value: "grand_total",
        fieldname: "grand_total",
        fieldtype: "Currency",
      },
    ];

    const compile = (
      fieldname: string,
      operator: FieldConditionValue["operator"],
      value: FieldConditionValue["value"]
    ) =>
      toConditionExpression(group([leaf(fieldname, operator, value)]), {
        fields,
      });

    it("compiles a Check field to its truthiness and a Data field to a comparison", () => {
      expect(compile("is_open", "equals", "Yes")).toBe("is_open");
      expect(compile("is_open", "equals", "No")).toBe("not is_open");
      // Without fields this would read as a Check, since the value is the word.
      expect(compile("subject", "equals", "Yes")).toBe('subject == "Yes"');
    });

    it("compiles a numeric field's value to a number, not a quoted string", () => {
      // `doc.grand_total > "100"` raises under safe_eval rather than comparing.
      expect(compile("grand_total", ">", "100")).toBe("grand_total > 100");
      expect(compile("grand_total", "equals", "0")).toBe("grand_total == 0");
      // Not a number: quoted, so the expression still parses.
      expect(compile("grand_total", "equals", "lots")).toBe(
        'grand_total == "lots"'
      );
    });

    it("leaves an unknown fieldname to the value-only rules", () => {
      expect(compile("nonexistent", "equals", "Yes")).toBe(
        'nonexistent == "Yes"'
      );
    });

    it("compiles nothing for a membership test on a number", () => {
      // `"1" in doc.grand_total` raises, and safe_eval has no `str` to coerce
      // with: its whitelist is int/float/long/round.
      expect(compile("grand_total", "like", "100")).toBe("");
      expect(compile("grand_total", "not like", "100")).toBe("");
      // Still a membership test on anything that holds a string.
      expect(compile("subject", "like", "refund")).toBe(
        '(subject and "refund" in subject)'
      );
    });

    it("compiles a numeric field's list members as numbers", () => {
      // The document holds 100, and `100 in ["100"]` is False, so quoting the
      // members makes the row match nothing at all rather than raise, which is
      // the harder kind to notice.
      expect(compile("grand_total", "in", "100, 200")).toBe(
        "(grand_total and grand_total in [100, 200])"
      );
      // A member that is not a number stays quoted: `in` compares by equality
      // and answers False across types, so it costs that member, not the rule.
      expect(compile("grand_total", "in", "100, lots")).toBe(
        '(grand_total and grand_total in [100, "lots"])'
      );
      expect(compile("subject", "in", "a, b")).toBe(
        '(subject and subject in ["a", "b"])'
      );
    });

    it("compiles a numeric field's range ends as numbers", () => {
      expect(compile("grand_total", "between", ["100", "200"])).toBe(
        "(grand_total >= 100 and grand_total <= 200)"
      );
      // Both ends are ordering comparisons, and `100 >= "abc"` raises, so an
      // end that cannot be read as a number takes the row rather than the rule.
      expect(compile("grand_total", "between", ["abc", "200"])).toBe("");
    });

    it("compiles nothing for an ordering comparison it cannot make", () => {
      // `doc.grand_total > "lots"` is a TypeError, which loses every other
      // condition in the rule. `==` is left alone: Python compares across types
      // and answers False, so it is merely a row that never matches.
      expect(compile("grand_total", ">", "lots")).toBe("");
      expect(compile("grand_total", "<=", "")).toBe("");
      expect(compile("grand_total", "equals", "lots")).toBe(
        'grand_total == "lots"'
      );
    });
  });

  describe("values that would not survive being written into Python", () => {
    const fields: ConditionField[] = [
      {
        label: "Subject",
        value: "subject",
        fieldname: "subject",
        fieldtype: "Small Text",
      },
    ];

    const compile = (value: FieldConditionValue["value"]) =>
      toConditionExpression(group([leaf("subject", "equals", value)]), {
        fields,
      });

    it("escapes the characters that would end the literal early", () => {
      // A newline written through ends the string it is inside, so the whole
      // expression is a SyntaxError, and an unparseable rule matches nothing,
      // losing every other condition in the record along with this row. Reachable
      // from any Long Text, Small Text or Text Editor value.
      expect(compile(`a${String.fromCharCode(10)}b`)).toBe(
        'subject == "a\\nb"'
      );
      expect(compile(`a${String.fromCharCode(13)}b`)).toBe(
        'subject == "a\\rb"'
      );
      expect(compile(`a${String.fromCharCode(9)}b`)).toBe('subject == "a\\tb"');
      // Anything else in the control range escapes numerically.
      expect(compile(`a${String.fromCharCode(0)}b`)).toBe(
        'subject == "a\\x00b"'
      );
      expect(compile(`a${String.fromCharCode(7)}b`)).toBe(
        'subject == "a\\x07b"'
      );
    });

    it("still escapes the backslash before the quote", () => {
      expect(compile('a\\b"c')).toBe('subject == "a\\\\b\\"c"');
    });
  });

  describe("an operator with no rule", () => {
    it("compiles nothing for a between whose value names one end or none", () => {
      // What frappe-ui's DateRangePicker.clearSelection() leaves behind. Emitted
      // as `due_date between ""` it is a SyntaxError, which takes down the whole
      // rule rather than this one row.
      const one = (value: FieldConditionValue["value"]) =>
        toConditionExpression(group([leaf("due_date", "between", value)]));

      expect(one("")).toBe("");
      expect(one("2026-01-01")).toBe("");
      expect(one(["2026-01-01"])).toBe("");
      expect(one(["2026-01-01", "2026-01-31"])).toBe(
        '(due_date >= "2026-01-01" and due_date <= "2026-01-31")'
      );
    });

    it("compiles nothing for a between holding a pair of empty ends", () => {
      // The state every Date row starts in: `getDefaultOperator` is `between`
      // and `getDefaultValue` is null, so this is what a freshly picked Date
      // field compiles to before the range is filled. Falling through to the
      // unset-value rule made it `due_date`, which reads as "is set" and matches
      // every document that has a date at all, the opposite of matching none.
      const one = (value: FieldConditionValue["value"]) =>
        toConditionExpression(group([leaf("due_date", "between", value)]));

      expect(one(null)).toBe("");
      // `DateRangePicker.clearSelection()` emits this, which the value type
      // does not admit and the compiler still has to survive.
      expect(one([null, null] as unknown as FieldConditionValue["value"])).toBe(
        ""
      );
      expect(one(["", ""])).toBe("");
      expect(one(["2026-01-01", ""])).toBe("");
      expect(one(["", "2026-01-31"])).toBe("");
    });

    it("compiles nothing for an in whose list names no member", () => {
      // Where `defaultValueFor` starts an option field the moment `in` or
      // `not in` is picked. `not in []` is True of every document that has the
      // field, so the rule fired on all of them before a value was chosen, and
      // `in []` is False for every one.
      const one = (
        operator: FieldConditionValue["operator"],
        value: FieldConditionValue["value"]
      ) => toConditionExpression(group([leaf("status", operator, value)]));

      expect(one("in", [])).toBe("");
      expect(one("not in", [])).toBe("");
      expect(one("in", "")).toBe("");
      expect(one("not in", "")).toBe("");
      expect(one("in", ["", ""])).toBe("");
      expect(one("in", ["Open"])).toBe('(status and status in ["Open"])');
      // A blank member beside a real one goes, and takes nothing with it: the
      // `status and` guard already excludes the documents it could have matched.
      expect(one("in", ["Open", ""])).toBe('(status and status in ["Open"])');
    });

    it("compiles nothing for a like with no pattern", () => {
      // Where a fresh text row starts: `like` is `getDefaultOperator`'s answer
      // for a Data field and the value beside it is the empty string. `"" in
      // doc.subject` is True of every document that has one, so this read as
      // "is set"; `not like ""` is False for every document and lost the rule.
      const one = (
        operator: FieldConditionValue["operator"],
        value: FieldConditionValue["value"]
      ) => toConditionExpression(group([leaf("subject", operator, value)]));

      expect(one("like", "")).toBe("");
      expect(one("not like", "")).toBe("");
      expect(one("like", null)).toBe("");
      expect(one("like", "refund")).toBe('(subject and "refund" in subject)');
    });

    it("compiles nothing for is against something other than set/not set", () => {
      expect(toConditionExpression(group([leaf("status", "is", "Open")]))).toBe(
        ""
      );
    });

    it("drops a stored timespan on read, so none reaches the compiler", () => {
      // `timespan` has no safe_eval expression at all, so it is not in
      // READ_OPERATOR: the entry is unparseable and goes the way of any other.
      const tree = fromFrappeConditions([
        ["status", "==", "Open"],
        "and",
        ["due_date", "timespan", "last week"],
      ]);

      expect(tree).toEqual(group([leaf("status", "equals", "Open")]));
      expect(toConditionExpression(tree)).toBe('status == "Open"');
    });

    it("keeps the level readable when a row compiles to nothing", () => {
      const tree = group(
        [
          leaf("status", "equals", "Open"),
          leaf("due_date", "between", ""),
          leaf("priority", "equals", "High"),
        ],
        "or"
      );

      expect(toConditionExpression(tree)).toBe(
        'status == "Open" or priority == "High"'
      );
    });
  });

  it("drops what the array drops, and the conjunction beside it", () => {
    const tree = group(
      [
        leaf("status", "equals", "Open"),
        // Added but never given a field: dropped on save, so dropped here.
        leaf("", "equals", ""),
        leaf("priority", "equals", "High"),
      ],
      "or"
    );

    expect(toConditionExpression(tree)).toBe(
      'status == "Open" or priority == "High"'
    );
  });

  it("drops an empty group without leaving its operator dangling", () => {
    const tree = group([group([]), leaf("status", "equals", "Open")], "and");

    expect(toConditionExpression(tree)).toBe('status == "Open"');
  });

  it("drops an entry it cannot parse, and the conjunction beside it", () => {
    // A doctype-qualified filter has no row to render and no Python to compile
    // to, so the reader drops it rather than carrying a leaf nothing can edit.
    const tree = fromFrappeConditions([
      ["status", "==", "Open"],
      "and",
      ["HD Ticket", "priority", "==", "High"],
    ]);

    expect(toConditionExpression(tree)).toBe('status == "Open"');
  });
});

describe("toFrappeConditions / fromFrappeConditions", () => {
  it("round-trips a nested tree through the stored array", () => {
    const tree = group(
      [
        leaf("status", "equals", "Open"),
        group(
          [leaf("priority", "equals", "High"), leaf("agent", "is", "not set")],
          "or"
        ),
      ],
      "and"
    );

    const stored = toFrappeConditions(tree);

    expect(stored).toEqual([
      ["status", "equals", "Open"],
      "and",
      [["priority", "equals", "High"], "or", ["agent", "is", "not set"]],
    ]);
    expect(fromFrappeConditions(stored)).toEqual(tree);
  });

  it("drops a leading entry it cannot parse without stranding its operator", () => {
    // The dropped entry takes the token that followed it: kept, it would join
    // the level's first survivor to nothing and re-save as a leading `or`.
    expect(
      fromFrappeConditions([
        ["HD Ticket", "status", "==", "Open"],
        "or",
        ["priority", "==", "High"],
      ])
    ).toEqual(group([leaf("priority", "equals", "High")]));
  });

  it("keeps one gap per pair when a record repeats a token", () => {
    expect(
      fromFrappeConditions([
        ["status", "==", "Open"],
        "and",
        "or",
        ["priority", "==", "High"],
      ])
    ).toEqual(
      group(
        [leaf("status", "equals", "Open"), leaf("priority", "equals", "High")],
        "or"
      )
    );
  });

  it("writes the group's one token between every surviving pair", () => {
    const tree = group(
      [
        leaf("status", "equals", "Open"),
        leaf("priority", "equals", "High"),
        leaf("agent", "equals", "sam"),
      ],
      "or"
    );

    expect(toFrappeConditions(tree)).toEqual([
      ["status", "equals", "Open"],
      "or",
      ["priority", "equals", "High"],
      "or",
      ["agent", "equals", "sam"],
    ]);
  });

  describe("a stored level that mixes and with or", () => {
    // The array can hold a token per gap; a group holds one. The first
    // separator wins and the rest are discarded, so what loads is not what was
    // stored. This is the lossy half of the model, pinned here so it cannot
    // change silently.
    const mixed = [
      ["status", "==", "Open"],
      "and",
      ["priority", "==", "High"],
      "or",
      ["agent", "==", "sam"],
    ];

    it("takes the first token and discards the rest", () => {
      expect(fromFrappeConditions(mixed)).toEqual(
        group(
          [
            leaf("status", "equals", "Open"),
            leaf("priority", "equals", "High"),
            leaf("agent", "equals", "sam"),
          ],
          "and"
        )
      );
    });

    it("re-saves as a different rule than it loaded", () => {
      // `A and B or C` was stored; `A and B and C` is what a save writes back.
      // Accepted, and stated in the reader's doc comment and in the README.
      expect(toFrappeConditions(fromFrappeConditions(mixed))).toEqual([
        ["status", "equals", "Open"],
        "and",
        ["priority", "equals", "High"],
        "and",
        ["agent", "equals", "sam"],
      ]);
    });

    it("normalises each level by its own first token", () => {
      expect(
        fromFrappeConditions([
          ["status", "==", "Open"],
          "or",
          [
            ["priority", "==", "High"],
            "and",
            ["agent", "==", "sam"],
            "or",
            ["team", "==", "billing"],
          ],
          "and",
          ["subject", "like", "refund"],
        ])
      ).toEqual(
        group(
          [
            leaf("status", "equals", "Open"),
            group(
              [
                leaf("priority", "equals", "High"),
                leaf("agent", "equals", "sam"),
                leaf("team", "equals", "billing"),
              ],
              "and"
            ),
            leaf("subject", "like", "refund"),
          ],
          "or"
        )
      );
    });

    it("compiles the flattened rule, agreeing with what a save writes", () => {
      // The expression is compiled from the array the tree writes, not from the
      // one that was read, so the two halves of the record still agree with
      // each other. They just no longer agree with what was stored.
      expect(toConditionExpression(fromFrappeConditions(mixed))).toBe(
        'status == "Open" and priority == "High" and agent == "sam"'
      );
    });
  });
});
