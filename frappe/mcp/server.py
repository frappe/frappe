"""Create an official SDK server for one Frappe request."""

from mcp.server import MCPServer

import frappe


def create_server():
	return MCPServer("frappe", version=frappe.__version__, subscriptions=False)
