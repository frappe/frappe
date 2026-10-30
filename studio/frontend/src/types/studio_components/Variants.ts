/**
 * A container that renders one of its children. Each child is an option and names itself with a
 * `variantOptionName` key beside `componentName`. An unnamed child falls back to "Option N".
 * There is no options prop: the option blocks hold the names.
 */
export interface VariantsProps {
	/** Names the set on the variants pill, so two sets on one page can be told apart. */
	name: string
}
