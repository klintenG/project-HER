/**
 * Copilot Bridge Extension
 * 
 * Exposes VS Code's GitHub Copilot Language Model API as a local HTTP server
 * so external applications (like our Python pipeline) can use Claude Opus 4.6
 * and other Copilot-provided models.
 * 
 * Endpoints:
 *   GET  /health          → { status: "ok", models: [...] }
 *   GET  /models          → list available LM models
 *   POST /chat            → generate a completion
 *        body: { system_prompt, user_prompt, model?, temperature?, max_tokens? }
 *        response: { content, model, tokens_used }
 */

const vscode = require('vscode');
const http = require('http');

let server = null;
let statusBarItem = null;

/**
 * Find the best available model matching a preferred family.
 */
async function selectModel(preferredFamily) {
    // Try preferred model first
    if (preferredFamily) {
        try {
            const models = await vscode.lm.selectChatModels({ family: preferredFamily });
            if (models && models.length > 0) {
                return models[0];
            }
        } catch (e) {
            // Fall through to broader search
        }
    }

    // Try common model families in order of preference
    const families = [
        'claude-sonnet-4',
        'claude-3.5-sonnet', 
        'gpt-4o',
        'gpt-4',
        'claude-3-opus',
        'o4-mini',
        'o3-mini',
    ];

    for (const family of families) {
        try {
            const models = await vscode.lm.selectChatModels({ family });
            if (models && models.length > 0) {
                return models[0];
            }
        } catch (e) {
            continue;
        }
    }

    // Last resort: grab any available model
    try {
        const allModels = await vscode.lm.selectChatModels();
        if (allModels && allModels.length > 0) {
            return allModels[0];
        }
    } catch (e) {
        // No models available at all
    }

    return null;
}

/**
 * List all available models for the /models endpoint.
 */
async function listModels() {
    try {
        const models = await vscode.lm.selectChatModels();
        return (models || []).map(m => ({
            id: m.id,
            family: m.family,
            vendor: m.vendor,
            name: m.name,
            maxInputTokens: m.maxInputTokens,
        }));
    } catch (e) {
        return [];
    }
}

/**
 * Handle a chat completion request.
 */
async function handleChat(body) {
    const { system_prompt, user_prompt, model: modelFamily, temperature, max_tokens } = body;

    if (!user_prompt) {
        return { error: 'user_prompt is required', status: 400 };
    }

    // Select model
    const preferredFamily = modelFamily || vscode.workspace.getConfiguration('copilotBridge').get('preferredModel');
    const selectedModel = await selectModel(preferredFamily);

    if (!selectedModel) {
        return { 
            error: 'No language models available. Ensure GitHub Copilot Chat is installed and authenticated.', 
            status: 503 
        };
    }

    // Build messages
    const messages = [];
    
    if (system_prompt) {
        messages.push(vscode.LanguageModelChatMessage.User(
            `[System Instructions]\n${system_prompt}\n\n[End System Instructions]\n\nNow respond to the following:`
        ));
    }
    
    messages.push(vscode.LanguageModelChatMessage.User(user_prompt));

    // Send request
    try {
        const options = {};
        // Note: VS Code LM API may not support all options depending on the model
        // Temperature and max_tokens are model-dependent

        const response = await selectedModel.sendRequest(messages, options);

        // Collect streamed response
        let content = '';
        for await (const chunk of response.text) {
            content += chunk;
        }

        return {
            content,
            model: selectedModel.id,
            family: selectedModel.family,
            vendor: selectedModel.vendor,
            status: 200,
        };
    } catch (e) {
        if (e instanceof vscode.LanguageModelError) {
            return { 
                error: `LM Error (${e.code}): ${e.message}`, 
                status: 502 
            };
        }
        return { error: e.message, status: 500 };
    }
}

/**
 * Parse JSON body from an HTTP request.
 */
function parseBody(req) {
    return new Promise((resolve, reject) => {
        let data = '';
        req.on('data', chunk => { data += chunk; });
        req.on('end', () => {
            try {
                resolve(data ? JSON.parse(data) : {});
            } catch (e) {
                reject(new Error('Invalid JSON'));
            }
        });
        req.on('error', reject);
    });
}

/**
 * Start the HTTP bridge server.
 */
function startServer(port) {
    if (server) {
        return; // Already running
    }

    server = http.createServer(async (req, res) => {
        // CORS headers for local development
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
        res.setHeader('Content-Type', 'application/json');

        if (req.method === 'OPTIONS') {
            res.writeHead(204);
            res.end();
            return;
        }

        try {
            // GET /health
            if (req.method === 'GET' && req.url === '/health') {
                const models = await listModels();
                res.writeHead(200);
                res.end(JSON.stringify({ 
                    status: 'ok', 
                    bridge: 'copilot-bridge',
                    models_available: models.length,
                    models: models.map(m => m.family),
                }));
                return;
            }

            // GET /models
            if (req.method === 'GET' && req.url === '/models') {
                const models = await listModels();
                res.writeHead(200);
                res.end(JSON.stringify({ models }));
                return;
            }

            // POST /chat
            if (req.method === 'POST' && req.url === '/chat') {
                const body = await parseBody(req);
                const result = await handleChat(body);
                const statusCode = result.status || 200;
                delete result.status;
                res.writeHead(statusCode);
                res.end(JSON.stringify(result));
                return;
            }

            // 404
            res.writeHead(404);
            res.end(JSON.stringify({ error: 'Not found. Use GET /health, GET /models, or POST /chat' }));

        } catch (e) {
            res.writeHead(500);
            res.end(JSON.stringify({ error: e.message }));
        }
    });

    server.listen(port, '127.0.0.1', () => {
        const msg = `Copilot Bridge running on http://127.0.0.1:${port}`;
        console.log(msg);
        vscode.window.showInformationMessage(`🌉 ${msg}`);
        updateStatusBar(port);
    });

    server.on('error', (e) => {
        if (e.code === 'EADDRINUSE') {
            vscode.window.showWarningMessage(`Copilot Bridge: Port ${port} is already in use. Trying ${port + 1}...`);
            server = null;
            startServer(port + 1);
        } else {
            vscode.window.showErrorMessage(`Copilot Bridge error: ${e.message}`);
        }
    });
}

/**
 * Stop the HTTP bridge server.
 */
function stopServer() {
    if (server) {
        server.close();
        server = null;
        vscode.window.showInformationMessage('🌉 Copilot Bridge stopped');
        updateStatusBar(null);
    }
}

/**
 * Update the status bar indicator.
 */
function updateStatusBar(port) {
    if (!statusBarItem) {
        statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    }
    if (port) {
        statusBarItem.text = `$(radio-tower) Bridge :${port}`;
        statusBarItem.tooltip = `Copilot Bridge running on port ${port}`;
        statusBarItem.command = 'copilotBridge.status';
        statusBarItem.backgroundColor = undefined;
    } else {
        statusBarItem.text = '$(radio-tower) Bridge OFF';
        statusBarItem.tooltip = 'Copilot Bridge is stopped';
        statusBarItem.command = 'copilotBridge.start';
    }
    statusBarItem.show();
}

/**
 * Extension activation.
 */
function activate(context) {
    console.log('Copilot Bridge extension activating...');

    const config = vscode.workspace.getConfiguration('copilotBridge');
    const port = config.get('port', 18945);
    const autoStart = config.get('autoStart', true);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('copilotBridge.start', () => {
            const p = vscode.workspace.getConfiguration('copilotBridge').get('port', 18945);
            startServer(p);
        }),
        vscode.commands.registerCommand('copilotBridge.stop', () => {
            stopServer();
        }),
        vscode.commands.registerCommand('copilotBridge.status', async () => {
            const models = await listModels();
            const running = server !== null;
            const modelList = models.map(m => `  • ${m.family} (${m.vendor})`).join('\n');
            
            vscode.window.showInformationMessage(
                `Copilot Bridge: ${running ? 'Running ✅' : 'Stopped ❌'}\n` +
                `Available models (${models.length}):\n${modelList || '  None'}`,
                { modal: true }
            );
        })
    );

    // Auto-start if configured
    if (autoStart) {
        // Small delay to let Copilot extension fully initialize
        setTimeout(() => startServer(port), 3000);
    }

    updateStatusBar(null);
}

/**
 * Extension deactivation.
 */
function deactivate() {
    stopServer();
    if (statusBarItem) {
        statusBarItem.dispose();
    }
}

module.exports = { activate, deactivate };
