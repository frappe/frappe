/**
 * Builds src/data/cssPropertyMetadata.json from mdn-data + web-features so the app ships a
 * trimmed lookup instead of parsing MDN syntax grammars at runtime.
 * Run it after bumping either dependency: `yarn generate:css-metadata`.
 */
import fs from "node:fs";
import { createRequire } from "node:module";
import { features } from "web-features";

const require = createRequire(import.meta.url);
const cssProperties = require("mdn-data/css/properties.json");
const cssSyntaxes = require("mdn-data/css/syntaxes.json");

const MAX_KEYWORDS = 40;
const KEYWORD_PATTERN = /^-?[_a-zA-Z][-_a-zA-Z0-9]*$/;

const isBaseline = (value) => value === "high" || value === "low";

const isBaselineProperty = (property) => {
	const compatKey = `css.properties.${property}`;
	return Object.values(features).some((feature) => {
		const compatStatus = feature.status?.by_compat_key?.[compatKey];
		if (compatStatus) return isBaseline(compatStatus.baseline);
		if (!feature.compat_features?.includes(compatKey)) return false;
		return isBaseline(feature.status?.baseline);
	});
};

const getSyntax = (property) => cssProperties[property]?.syntax || "";

const getKeywords = (syntax, seen = new Set()) => {
	const keywords = new Set();
	if (!syntax || seen.has(syntax)) return keywords;
	seen.add(syntax);

	const references = syntax.match(/<[-_a-zA-Z0-9()]+>/g) || [];
	references.forEach((reference) => {
		const referencedSyntax = cssSyntaxes[reference.slice(1, -1)]?.syntax;
		if (referencedSyntax) getKeywords(referencedSyntax, seen).forEach((keyword) => keywords.add(keyword));
	});

	// shorthands (eg. text-decoration) reference their longhands by quoted property name
	const propertyReferences = syntax.match(/<'[^']+'>/g) || [];
	propertyReferences.forEach((reference) => {
		const property = reference.slice(2, -2);
		getKeywords(getSyntax(property), seen).forEach((keyword) => keywords.add(keyword));
	});

	syntax
		.replace(/<[^>]+>/g, " ")
		.replace(/[,[\]{}()?*+#/]/g, " ")
		.split(/\s*\|\|\s*|\s*\|\s*|\s+/)
		.map((part) => part.trim())
		.filter((part) => KEYWORD_PATTERN.test(part) && !part.includes("_separator"))
		.forEach((keyword) => keywords.add(keyword));

	return keywords;
};

// components combined with || or && are independent value slots (eg. text-decoration's
// line/style/color/thickness), so the shorthand is only color-like if every slot is
const isColorLike = (syntax, seen = new Set()) => {
	const components = syntax.split(/\s*(?:\|\||&&)\s*/).filter(Boolean);
	if (components.length > 1) return components.every((component) => isColorLike(component, new Set(seen)));

	if (syntax.includes("<color>")) return true;
	const propertyReferences = syntax.match(/<'[^']+'>/g) || [];
	return propertyReferences.some((reference) => {
		const property = reference.slice(2, -2);
		if (seen.has(property)) return false;
		seen.add(property);
		return isColorLike(getSyntax(property), seen);
	});
};

// the value shape a property accepts, which decides the control the editor renders
const getKind = (property) => {
	const syntax = getSyntax(property);
	if (isColorLike(syntax)) return "color";
	if (/<length|<length-percentage|<percentage|<line-width|<flex>/.test(syntax)) return "length";
	if (syntax.includes("<integer>")) return "integer";
	if (/<number>|<opacity-value>|<alpha-value>/.test(syntax)) return "number";
	return "keyword";
};

// expanding <color> floods any property that merely accepts one (filter, box-shadow, mask...)
// with 150 named colors, so it is marked as already-seen and left unexpanded
const colorSyntax = cssSyntaxes.color?.syntax;

const buildEntry = (property) => {
	const entry = { kind: getKind(property) };
	if (entry.kind !== "color") {
		const keywords = Array.from(getKeywords(getSyntax(property), new Set([colorSyntax]))).slice(
			0,
			MAX_KEYWORDS,
		);
		if (keywords.length) entry.keywords = keywords;
	}
	if (isBaselineProperty(property)) entry.baseline = true;
	return entry;
};

const metadata = Object.entries(cssProperties)
	.filter(([property, data]) => data.status === "standard" && !property.startsWith("-"))
	.map(([property]) => property)
	.sort()
	.reduce((accumulator, property) => {
		accumulator[property] = buildEntry(property);
		return accumulator;
	}, {});

fs.mkdirSync(new URL("../src/data/", import.meta.url), { recursive: true });
fs.writeFileSync(new URL("../src/data/cssPropertyMetadata.json", import.meta.url), JSON.stringify(metadata));
