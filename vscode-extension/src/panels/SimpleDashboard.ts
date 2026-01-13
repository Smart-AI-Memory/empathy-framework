import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export class SimpleDashboardProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'empathy-simple-dashboard';
    private _view?: vscode.WebviewView;

    constructor(private readonly _extensionUri: vscode.Uri) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this.getHtmlForWebview(webviewView.webview);

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage((message) => {
            switch (message.type) {
                case 'refresh':
                    this.updateData();
                    break;
            }
        });

        // Send initial data immediately
        this.updateData();
    }

    private updateData() {
        if (!this._view) {
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            return;
        }

        // Load health data
        const healthFile = path.join(workspaceFolder, '.empathy', 'health.json');
        let healthScore = '--';
        let patterns = '--';

        try {
            if (fs.existsSync(healthFile)) {
                const healthData = JSON.parse(fs.readFileSync(healthFile, 'utf8'));
                healthScore = healthData.score?.toString() || '--';
            }
        } catch (e) {
            console.error('Failed to load health:', e);
        }

        // Load patterns data
        const patternsFile = path.join(workspaceFolder, 'patterns', 'debugging.json');
        try {
            if (fs.existsSync(patternsFile)) {
                const patternsData = JSON.parse(fs.readFileSync(patternsFile, 'utf8'));
                patterns = patternsData.patterns?.length?.toString() || '0';
            }
        } catch (e) {
            console.error('Failed to load patterns:', e);
        }

        // Send data to webview
        this._view.webview.postMessage({
            type: 'update',
            healthScore,
            patterns
        });
    }

    private getHtmlForWebview(webview: vscode.Webview): string {
        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <title>Empathy Dashboard</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            padding: 20px;
            color: var(--vscode-foreground);
        }
        .stat {
            background: var(--vscode-input-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 4px;
            padding: 16px;
            margin-bottom: 12px;
        }
        .stat-label {
            font-size: 12px;
            opacity: 0.7;
            margin-bottom: 4px;
        }
        .stat-value {
            font-size: 24px;
            font-weight: 600;
        }
        button {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin-top: 12px;
        }
        button:hover {
            background: var(--vscode-button-hoverBackground);
        }
    </style>
</head>
<body>
    <h2>Empathy Dashboard</h2>

    <div class="stat">
        <div class="stat-label">Health Score</div>
        <div class="stat-value" id="health-score">Loading...</div>
    </div>

    <div class="stat">
        <div class="stat-label">Patterns</div>
        <div class="stat-value" id="patterns">Loading...</div>
    </div>

    <button id="refresh-btn">Refresh</button>

    <script nonce="${nonce}">
        const vscode = acquireVsCodeApi();

        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;
            if (message.type === 'update') {
                document.getElementById('health-score').textContent = message.healthScore;
                document.getElementById('patterns').textContent = message.patterns;
            }
        });

        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            vscode.postMessage({ type: 'refresh' });
        });
    </script>
</body>
</html>`;
    }
}

function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
