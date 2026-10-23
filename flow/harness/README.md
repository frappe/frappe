# Flow

Flow is an extensible open-source agent harness.

## Install

Flow requires Python 3.14 or newer.

```sh
uv tool install frappe-flow
# or: pip install frappe-flow
```

## Run

```sh
flow
```

## Commands

| Command | Description |
|---|---|
| `flow` or `flow web` | Start the web interface. |
| `flow tui` | Start the terminal interface. |
| `flow tui -c` | Continue the latest session for the current directory. |
| `flow serve` | Run the server. |
| `flow attach` | Attach the terminal interface to a running server. |
| `flow providers` | Show providers and their authentication status. |
| `flow login <provider>` | Configure a provider. |
| `flow logout <provider>` | Remove a provider credential. |

Run `flow --help` for all options.

## License

MIT
