# Tailwind scans the module list, not a glob

Tailwind writes no rule for a class it never scanned. Nothing throws. The
component renders unstyled, in a way that reads like a design choice.

The mistake that causes it is always the same shape: the stylesheet is scanned
from a *description* of what the bundle holds, while something else assembles the
bundle. A `content` list that names `.vue` files misses the `.ts` helper holding
the class literals. A list that names the app's own source misses frappe-ui,
whose components apply classes on every island.

## Decision

The preset scans the modules the bundle is built from. It runs a first build with
no stylesheet, keeps the module list, and throws the output away. There is no
`content` option for an app to keep.

The list is the bundle, so it cannot drift from the bundle. It covers the app's
source and every dependency compiled into it, because the island's stylesheet is
the only one inside its shadow root and has to carry a rule for every class the
bundle applies.

The second pass costs about the time of the first, and there is one pass per app
rather than one per island
([0002](0002-an-app-builds-its-islands-together.md)).

## Rejected: a glob wide enough to be safe

Scanning all of an app's source instead of the module list took one island's
stylesheet from 32 kB to 259 kB — the classes of every screen the island does not
render.

## Rejected: scan the built JS for class names

It finds the same bugs and a pile of noise. A chunk carries its components'
compiled CSS as a string, and the escaped selectors in it read as class names
that are already defined a line away.

## The check, for the case the derivation does not cover

A full build derives the scan list from the bundle, so the two cannot disagree.
Under `watch` they can: the list is fixed at start-up, and an import added since
brings in a file nothing has scanned. So the preset compares the bundle's module
list against the scanned list and fails the build on a file in the first and not
the second. Restart the watch to pick it up.

The comparison is over files, not classes, and both lists are real paths. The
preset wrote the scanned list itself, so this is set membership and needs no glob
engine.
