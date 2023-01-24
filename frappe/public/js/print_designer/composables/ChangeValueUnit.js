import { parseFloatAndUnit } from "../utils";
/**
 *
 * @param {{inputString: String, defaultInputUnit: 'px'|'mm'|'cm'|'in',  convertionUnit: 'px'|'mm'|'cm'|'in'}} `px is considered by default for defaultInputUnit and convertionUnit`
 * @example
 * useChangeValueUnit("210 mm", "in") : {
 *  value: 8.26771653553125,
 *  unit: in,
 *  error: false
 * }
 * @returns {{value: Number, unit: String, error: Boolean}} converted value based on unit parameters
 */
export function useChangeValueUnit({
	inputString,
	defaultInputUnit = "px",
	convertionUnit = "px",
}) {
	const parsedInput = parseFloatAndUnit(inputString, defaultInputUnit || convertionUnit);
	const UnitValues = Object.freeze({
		px: 1,
		mm: 3.7795275591,
		cm: 37.795275591,
		in: 96,
	});
	const converstionFactor = Object.freeze({
		from_px: {
			to_px: 1,
			to_mm: UnitValues.px / UnitValues.mm,
			to_cm: UnitValues.px / UnitValues.cm,
			to_in: UnitValues.px / UnitValues.in,
		},
		from_mm: {
			to_mm: 1,
			to_px: UnitValues.mm / UnitValues.px,
			to_cm: UnitValues.mm / UnitValues.cm,
			to_in: UnitValues.mm / UnitValues.in,
		},
		from_cm: {
			to_cm: 1,
			to_px: UnitValues.cm / UnitValues.px,
			to_mm: UnitValues.cm / UnitValues.mm,
			to_in: UnitValues.cm / UnitValues.in,
		},
		from_in: {
			to_in: 1,
			to_px: UnitValues.in / UnitValues.px,
			to_mm: UnitValues.in / UnitValues.mm,
			to_cm: UnitValues.in / UnitValues.cm,
		},
	});
	return {
		value:
			parsedInput.value *
			converstionFactor[`from_${parsedInput.unit}`][`to_${convertionUnit}`],
		unit: convertionUnit,
		error: [NaN, null, undefined].includes(parsedInput.value),
	};
}
