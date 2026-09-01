// The operator table is composed rather than copied, per ADR-0008.
import { getOperators } from "../../Filter/operators";
import type { OperatorOption } from "../../Filter/operators";
import type { ConditionOperator, ConditionOperatorOption } from "../types";

// Everything this component knows about an operator is here.
export interface OperatorRule {
  /** Stored tokens that also read as this operator, besides its own name. */
  reads?: string[];
  /** The Python token, where Python spells it differently. */
  python?: string;
  /**
   * May be emitted as `field <op> value`. An operator reaching the end of
   * `compileLeaf` without one compiles to nothing: an unparseable expression
   * matches nothing at all, losing every other condition with it.
   */
  scalar?: boolean;
  /**
   * Python refuses these across types: `1 > "1"` raises where `1 == "1"` is
   * merely False.
   */
  ordering?: boolean;
}

/** A full `Record`, so an operator added to `Filter` fails the build here
 *  until it is given a rule, rather than compiling to nothing. */
export const OPERATORS: Record<ConditionOperator, OperatorRule> = {
  equals: { reads: ["==", "="], python: "==", scalar: true },
  "not equals": { reads: ["!="], python: "!=", scalar: true },
  like: {},
  "not like": {},
  in: {},
  "not in": {},
  is: {},
  "is not": {},
  "<": { scalar: true, ordering: true },
  ">": { scalar: true, ordering: true },
  "<=": { scalar: true, ordering: true },
  ">=": { scalar: true, ordering: true },
  between: {},
};

/** Every stored token this parser accepts, and the operator it reads as. */
export const READ_OPERATOR: Record<string, ConditionOperator> =
  Object.fromEntries(
    Object.entries(OPERATORS).flatMap(([name, rule]) =>
      [name, ...(rule.reads ?? [])].map((token) => [
        token,
        name as ConditionOperator,
      ])
    )
  );

/** A rule's Python token, which is its own name unless it says otherwise. */
export function pythonToken(name: string, rule: OperatorRule): string {
  return rule.python ?? name;
}

function pythonTokensWhere(
  wanted: (rule: OperatorRule) => boolean | undefined
): string[] {
  return Object.entries(OPERATORS)
    .filter(([, rule]) => wanted(rule))
    .map(([name, rule]) => pythonToken(name, rule));
}

export const SCALAR_COMPARISONS = pythonTokensWhere((rule) => rule.scalar);
export const ORDERING = pythonTokensWhere((rule) => rule.ordering);

/** Fieldtypes whose value is a number in the document, not a string. */
export const NUMERIC_FIELDTYPES = [
  "Int",
  "Float",
  "Currency",
  "Percent",
  "Rating",
];

const IS_NOT: ConditionOperatorOption = { label: "Is not", value: "is not" };

/** The operators this component can write, for a field of this type. */
export function conditionOperators(
  fieldtype: string,
  fieldname?: string
): ConditionOperatorOption[] {
  const offered = getOperators(fieldtype, fieldname).filter(isWritable);
  const is = offered.findIndex((option) => option.value === "is");
  if (is !== -1) offered.splice(is + 1, 0, IS_NOT);
  return offered;
}

function isWritable(option: OperatorOption): option is ConditionOperatorOption {
  return option.value !== "timespan";
}
