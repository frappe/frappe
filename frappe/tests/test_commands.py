# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors

from __future__ import unicode_literals

import shlex
import subprocess
import unittest

import frappe


def clean(value):
	if isinstance(value, (bytes, str)):
		value = value.decode().strip()
	return value


class BaseTestCommands:
	def execute(self, command):
		command = command.format(**{"site": frappe.local.site})
		command = shlex.split(command)
		self._proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		self.stdout = clean(self._proc.stdout)
		self.stderr = clean(self._proc.stderr)
		self.returncode = clean(self._proc.returncode)
