"""Run from the bench root: env/bin/python -m frappe.mcp.demo_client SITE_URL."""

import argparse
import json
import os

import anyio
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


async def run_demo(url, mode, write_demo):
	authorization = os.environ["FRAPPE_MCP_AUTHORIZATION"]
	async with httpx2.AsyncClient(headers={"Authorization": authorization}) as http:
		async with Client(
			streamable_http_client(url.rstrip("/") + "/api/mcp", http_client=http), mode=mode
		) as client:
			tools = await client.list_tools()
			print("Protocol:", client.protocol_version)
			print("Tools:", ", ".join(tool.name for tool in tools.tools))
			await show(client, "discover", {"doctype": "ToDo"})
			await show(client, "get_documents", {"doctype": "ToDo", "limit": 2})
			await show(client, "call_method", {"method": "frappe.auth.get_logged_user"})
			if write_demo:
				await document_round_trip(client)


async def document_round_trip(client):
	created = await show(
		client,
		"write_documents",
		{"action": "create", "doctype": "ToDo", "data": {"description": "MCP SDK demo"}},
	)
	name = created["document"]["name"]
	try:
		await show(client, "get_documents", {"doctype": "ToDo", "name": name})
		await show(
			client,
			"write_documents",
			{
				"action": "update",
				"doctype": "ToDo",
				"name": name,
				"data": {"description": "MCP SDK demo updated"},
			},
		)
	finally:
		await show(client, "write_documents", {"action": "delete", "doctype": "ToDo", "name": name})


async def show(client, tool, arguments):
	response = await client.call_tool(tool, arguments)
	if response.is_error:
		raise RuntimeError("\n".join(block.text for block in response.content if block.type == "text"))
	print(tool, json.dumps(response.structured_content, indent=2))
	return response.structured_content


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("site_url")
	parser.add_argument("--mode", choices=("auto", "legacy"), default="auto")
	parser.add_argument("--write-demo", action="store_true", help="Create, update, and delete one demo ToDo")
	args = parser.parse_args()
	anyio.run(run_demo, args.site_url, args.mode, args.write_demo)


if __name__ == "__main__":
	main()
