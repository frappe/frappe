#!/usr/bin/env node
// Installs the island toolchain, so that two island builds starting at once do
// not both install it into one node_modules.

import { installToolchain } from "./toolchain.js";

installToolchain();
