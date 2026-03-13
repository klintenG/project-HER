# Copilot LM Bridge — VS Code Extension

A lightweight VS Code extension that exposes GitHub Copilot's language models
to external applications via a local HTTP server.

## How It Works

1. VS Code loads this extension on startup
2. The extension starts an HTTP server on `http://127.0.0.1:18945`
3. Your app sends POST requests to `/chat` with standard messages
4. The extension translates them into `vscode.lm` API calls
5. Copilot processes the request and returns the response as JSON

**No API keys needed** — VS Code handles all authentication through your
GitHub account and Copilot subscription.

## Endpoints

| Method | Path      | Description                        |
|--------|-----------|------------------------------------|
| GET    | `/health` | Check if bridge is running         |
| GET    | `/models` | List available Copilot models      |
| POST   | `/chat`   | Send a chat completion request     |

### POST /chat — Request Body

```json
{
  "model": "gpt-4o",
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "What is the capital of France?" }
  ],
  "max_tokens": 3000
}
```

### Response

```json
{
  "content": "The capital of France is Paris.",
  "model": "gpt-4o",
  "vendor": "copilot",
  "usage": { "elapsed_ms": 1234 }
}
```

## Installation

The extension is installed by symlinking into VS Code's extensions directory:

```bash
# macOS / Linux
ln -s /path/to/project-HER/vscode-copilot-bridge ~/.vscode/extensions/copilot-bridge

# Then restart VS Code (or reload window: Cmd+Shift+P → "Reload Window")
```

## Requirements

- VS Code 1.90+
- GitHub Copilot Chat extension installed and signed in
- VS Code must be open while your app is running
