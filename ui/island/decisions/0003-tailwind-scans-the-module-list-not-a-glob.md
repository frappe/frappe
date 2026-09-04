# Tailwind scans the module list, not a glob

Tailwind writes no rule for a class it never scanned. Nothing throws. The component renders unstyled, in a way that reads like a design choice.

The mistake has one shape. Something describes what the bundle holds, and Tailwind scans that description, while something else assembles the bundle. A `content` list that names `.vue` files misses the `.ts` helper that holds the class literals. A list that names the app's own source misses frappe-ui, whose components apply classes on every island.

## Decision

The preset scans the modules the bundle is built from. It runs a first build with no stylesheet, keeps the module list, and discards the output. There is no `content` option for an app to keep.

The list is the bundle, so it cannot drift from the bundle. It covers the app's source and every dependency compiled into it. The island's stylesheet is the only one inside its shadow root, so it has to carry a rule for every class the bundle applies.

The second pass costs about the time of the first. There is one pass per app, not one per island ([0002](0002-an-app-builds-its-islands-together.md)).

## Rejected: a glob wide enough to be safe

A scan of all of an app's source took one island's stylesheet from 32 kB to 259 kB. The difference is the classes of every screen the island does not render.

## Rejected: scan the built JS for class names

It finds the same bugs and a pile of noise. A chunk carries its components' compiled CSS as a string. The escaped selectors in it read as class names, and those classes are already defined a line away.

## The check for the case the derivation does not cover

A full build derives the scan list from the bundle, so the two cannot disagree. Under `watch` they can. The list is fixed at start-up, and an import added after start-up brings in a file nothing scanned. So the preset compares the bundle's module list against the scanned list. If a file is in the first list and not the second, the preset fails the build. Restart the watch to scan it.

The comparison is over files, not classes. Both lists are real paths. The preset wrote the scanned list itself, so this is set membership and needs no glob engine.
