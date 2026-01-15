/**
 * Health Panel - Dedicated webview for health metrics
 *
 * Displays comprehensive health metrics including:
 * - Health score circle
 * - Patterns learned
 * - Lint, types, security, tests metrics
 * - Tech debt tracking
 * - Test coverage progress bar
 * - Quick action buttons
 *
 * Copyright 2025 Smart AI Memory, LLC
 * Licensed under Fair Source 0.9
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { getHealthDataService, HealthDataService } from '../services/HealthDataService';

export class HealthPanel {
    public static currentPanel: HealthPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private readonly _healthDataService: HealthDataService;

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._healthDataService = getHealthDataService();

        // Set the webview's initial html content
        this._update();

        // Listen for when the panel is disposed
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Handle messages from the webview
        this._panel.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.type) {
                    case 'refresh':
                        await this._updateData(true);
                        break;
                    case 'runCommand':
                        await this._runCommand(message.command);
                        break;
                    case 'openDashboard':
                        vscode.commands.executeCommand('empathy.dashboard');
                        break;
                }
            },
            null,
            this._disposables
        );

        // Auto-refresh data every 30 seconds
        const refreshInterval = setInterval(() => this._updateData(false), 30000);
        this._disposables.push({ dispose: () => clearInterval(refreshInterval) });
    }

    public static createOrShow(extensionUri: vscode.Uri) {
        const column = vscode.ViewColumn.One;

        // If we already have a panel, show it
        if (HealthPanel.currentPanel) {
            HealthPanel.currentPanel._panel.reveal(column);
            return;
        }

        // Otherwise, create a new panel
        const panel = vscode.window.createWebviewPanel(
            'empathyHealthPanel',
            'Health Metrics',
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    vscode.Uri.joinPath(extensionUri, 'webview'),
                ],
            }
        );

        HealthPanel.currentPanel = new HealthPanel(panel, extensionUri);
    }

    public dispose() {
        HealthPanel.currentPanel = undefined;

        // Clean up resources
        this._panel.dispose();

        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) {
                x.dispose();
            }
        }
    }

    private async _runCommand(command: string) {
        const commandMap: Record<string, string> = {
            'runScan': 'empathy.runScan',
            'fixAll': 'empathy.fixAll',
            'runTests': 'empathy.runTests',
            'securityScan': 'empathy.runSecurityScan',
            'learn': 'empathy.learn',
            'fixLint': 'empathy.fixLint',
        };

        const cmd = commandMap[command];
        if (cmd) {
            try {
                await vscode.commands.executeCommand(cmd);
                // Auto-refresh after command completes
                setTimeout(() => this._updateData(true), 1000);
            } catch (err) {
                vscode.window.showErrorMessage(`Command failed: ${err}`);
            }
        }
    }

    private async _updateData(force: boolean) {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            return;
        }

        const config = vscode.workspace.getConfiguration('empathy');
        const empathyDir = path.join(workspaceFolder, config.get<string>('empathyDir', '.empathy'));
        const patternsDir = path.join(workspaceFolder, config.get<string>('patternsDir', './patterns'));

        // Load health data from service
        const health = await this._healthDataService.getHealthData(empathyDir, patternsDir, force);

        // Send to webview
        this._panel.webview.postMessage({
            type: 'healthData',
            data: health
        });
    }

    private _update() {
        const webview = this._panel.webview;
        this._panel.title = 'Health Metrics';
        this._panel.webview.html = this._getHtmlForWebview(webview);
        this._updateData(false);
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <title>Health Metrics</title>
    <style>
        :root {
            --bg: var(--vscode-editor-background);
            --fg: var(--vscode-editor-foreground);
            --border: var(--vscode-panel-border);
            --button-bg: var(--vscode-button-background);
            --button-fg: var(--vscode-button-foreground);
            --button-hover: var(--vscode-button-hoverBackground);
            --success: var(--vscode-testing-iconPassed);
            --error: var(--vscode-testing-iconFailed);
            --warning: var(--vscode-editorWarning-foreground);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--fg);
            background: var(--bg);
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid var(--border);
        }

        .header h1 {
            font-size: 24px;
            font-weight: 600;
        }

        .header-actions {
            display: flex;
            gap: 10px;
        }

        .btn {
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
            background: var(--button-bg);
            color: var(--button-fg);
        }

        .btn:hover {
            background: var(--button-hover);
        }

        .btn:active {
            opacity: 0.8;
        }

        .score-container {
            padding: 12px;
            text-align: center;
        }

        .score-circle {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            font-weight: 700;
            margin: 0 auto 10px;
        }

        .score-circle.good { background: rgba(16, 185, 129, 0.2); color: var(--success); }
        .score-circle.warning { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
        .score-circle.bad { background: rgba(239, 68, 68, 0.2); color: var(--error); }

        .score-label {
            opacity: 0.7;
            font-size: 11px;
        }

        .card {
            background: var(--vscode-editor-inactiveSelectionBackground);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 15px;
        }

        .card-title {
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 10px;
            opacity: 0.9;
        }

        .health-tree {
            padding: 0 8px;
        }

        .tree-item {
            display: flex;
            align-items: center;
            padding: 6px 8px;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.2s;
        }

        .tree-item:hover {
            background: var(--vscode-list-hoverBackground);
        }

        .tree-icon {
            width: 20px;
            text-align: center;
            margin-right: 8px;
        }

        .tree-icon.ok { color: var(--success); }
        .tree-icon.warning { color: var(--warning); }
        .tree-icon.error { color: var(--error); }

        .tree-label {
            flex: 1;
            font-size: 12px;
        }

        .tree-value {
            font-size: 11px;
            opacity: 0.8;
            padding: 2px 6px;
            background: var(--vscode-input-background);
            border-radius: 3px;
        }

        .progress-bar {
            height: 20px;
            background: var(--vscode-input-background);
            border-radius: 4px;
            overflow: hidden;
            position: relative;
        }

        .progress-fill {
            height: 100%;
            transition: width 0.3s ease;
        }

        .progress-fill.success { background: var(--success); }
        .progress-fill.warning { background: var(--warning); }
        .progress-fill.error { background: var(--error); }

        .actions-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }

        .action-btn {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px;
            border: 1px solid var(--border);
            border-radius: 4px;
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }

        .action-btn:hover {
            background: var(--vscode-button-secondaryHoverBackground);
            transform: translateY(-1px);
        }

        .action-btn:active {
            transform: translateY(0);
        }

        .action-icon {
            font-size: 16px;
        }

        .last-updated {
            text-align: center;
            font-size: 11px;
            opacity: 0.6;
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Health Metrics</h1>
        <div class="header-actions">
            <button class="btn" onclick="openDashboard()">Dashboard</button>
            <button class="btn" onclick="refresh()">Refresh</button>
        </div>
    </div>

    <div class="score-container">
        <div class="score-circle good" id="health-score">--</div>
        <div class="score-label">Health Score (v2)</div>
    </div>

    <div class="card">
        <div class="card-title">Metrics</div>
        <div class="health-tree">
            <div class="tree-item" data-cmd="learn">
                <span class="tree-icon" id="patterns-icon">&#x2714;</span>
                <span class="tree-label">Patterns Learned</span>
                <span class="tree-value" id="metric-patterns">--</span>
            </div>
            <div class="tree-item" data-cmd="fixLint">
                <span class="tree-icon" id="lint-icon">&#x2714;</span>
                <span class="tree-label">Lint</span>
                <span class="tree-value" id="metric-lint">--</span>
            </div>
            <div class="tree-item" data-cmd="fixAll">
                <span class="tree-icon" id="types-icon">&#x2714;</span>
                <span class="tree-label">Types</span>
                <span class="tree-value" id="metric-types">--</span>
            </div>
            <div class="tree-item" data-cmd="securityScan">
                <span class="tree-icon" id="security-icon">&#x2714;</span>
                <span class="tree-label">Security</span>
                <span class="tree-value" id="metric-security">0 high</span>
            </div>
            <div class="tree-item" data-cmd="runTests">
                <span class="tree-icon" id="tests-icon">&#x2714;</span>
                <span class="tree-label">Tests</span>
                <span class="tree-value" id="metric-tests">--</span>
            </div>
            <div class="tree-item">
                <span class="tree-icon">&#x1F4DD;</span>
                <span class="tree-label">Tech Debt</span>
                <span class="tree-value" id="metric-debt">--</span>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="card-title">Coverage</div>
        <div style="display: flex; align-items: center; gap: 8px;">
            <div class="progress-bar" style="flex: 1">
                <div class="progress-fill success" id="coverage-bar" style="width: 0%"></div>
            </div>
            <span id="coverage-value">--%</span>
        </div>
    </div>

    <div class="card">
        <div class="card-title">Health Actions</div>
        <div class="actions-grid">
            <button class="action-btn" onclick="runAction('runScan')" title="Run v4.0 orchestrated health check with real analysis tools">
                <span class="action-icon">&#x1FA7A;</span>
                <span>Deep Scan</span>
            </button>
            <button class="action-btn" onclick="runAction('fixAll')" title="Apply safe auto-fixes (ruff --fix, formatting)">
                <span class="action-icon">&#x1F527;</span>
                <span>Auto Fix</span>
            </button>
            <button class="action-btn" onclick="runAction('runTests')" title="Run pytest test suite">
                <span class="action-icon">&#x1F9EA;</span>
                <span>Run Tests</span>
            </button>
            <button class="action-btn" onclick="runAction('securityScan')" title="Quick security vulnerability scan">
                <span class="action-icon">&#x1F512;</span>
                <span>Security Scan</span>
            </button>
        </div>
    </div>

    <div class="last-updated" id="last-updated">Last updated: --</div>

    <script nonce="${nonce}">
        const vscode = acquireVsCodeApi();

        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.type) {
                case 'healthData':
                    updateHealth(message.data);
                    break;
            }
        });

        function updateHealth(health) {
            if (!health) {
                document.getElementById('health-score').textContent = '--';
                return;
            }

            const scoreEl = document.getElementById('health-score');
            const score = health.score || 0;
            scoreEl.textContent = score + '%';
            scoreEl.className = 'score-circle ' + (score >= 80 ? 'good' : score >= 50 ? 'warning' : 'bad');

            // Update tree items with icons and values
            updateTreeItem('patterns', health.patterns || 0, (health.patterns || 0) > 0);
            updateTreeItem('lint', (health.lint?.errors || 0) + ' errors', (health.lint?.errors || 0) === 0);
            updateTreeItem('types', (health.types?.errors || 0) + ' errors', (health.types?.errors || 0) === 0);
            updateTreeItem('security', (health.security?.high || 0) + ' high', (health.security?.high || 0) === 0);
            updateTreeItem('tests', (health.tests?.passed || 0) + '/' + (health.tests?.total || 0), (health.tests?.failed || 0) === 0);
            document.getElementById('metric-debt').textContent = (health.techDebt?.total || 0) + ' items';

            const coverage = health.tests?.coverage || 0;
            document.getElementById('coverage-bar').style.width = coverage + '%';
            document.getElementById('coverage-bar').className = 'progress-fill ' + (coverage >= 70 ? 'success' : coverage >= 50 ? 'warning' : 'error');
            document.getElementById('coverage-value').textContent = coverage + '%';

            // Update last updated timestamp
            if (health.lastUpdated) {
                const date = new Date(health.lastUpdated);
                document.getElementById('last-updated').textContent = 'Last updated: ' + date.toLocaleString();
            }
        }

        function updateTreeItem(id, value, isOk) {
            const valueEl = document.getElementById('metric-' + id);
            const iconEl = document.getElementById(id + '-icon');
            if (valueEl) valueEl.textContent = value;
            if (iconEl) {
                iconEl.textContent = isOk ? '\\u2714' : '\\u2718';
                iconEl.className = 'tree-icon ' + (isOk ? 'ok' : 'error');
            }
        }

        // Track running actions
        const runningActions = new Set();

        // Tree item click handlers
        document.querySelectorAll('.tree-item[data-cmd]').forEach(item => {
            item.addEventListener('click', function() {
                const cmd = this.dataset.cmd;
                if (runningActions.has('tree-' + cmd)) return;

                runningActions.add('tree-' + cmd);
                this.style.opacity = '0.5';

                runAction(cmd);

                setTimeout(() => {
                    this.style.opacity = '1';
                    runningActions.delete('tree-' + cmd);
                }, 2000);
            });
        });

        function runAction(command) {
            // Find the button that triggered this (if it was a button click)
            const btn = event && event.target ? event.target.closest('.action-btn') : null;

            // Prevent duplicate clicks
            if (runningActions.has(command)) {
                return;
            }
            runningActions.add(command);

            // Show visual feedback on button
            if (btn) {
                const icon = btn.querySelector('.action-icon');
                const text = btn.querySelector('span:not(.action-icon)');
                const originalIcon = icon ? icon.innerHTML : '';
                const originalText = text ? text.textContent : '';

                btn.disabled = true;
                btn.style.opacity = '0.6';
                if (icon) icon.innerHTML = '⏳';
                if (text) text.textContent = 'Running...';

                setTimeout(() => {
                    btn.disabled = false;
                    btn.style.opacity = '1';
                    if (icon) icon.innerHTML = originalIcon;
                    if (text) text.textContent = originalText;
                    runningActions.delete(command);
                }, 3000);
            } else {
                // For tree items, remove from running set after delay
                setTimeout(() => {
                    runningActions.delete(command);
                }, 2000);
            }

            vscode.postMessage({
                type: 'runCommand',
                command: command
            });
        }

        function refresh() {
            vscode.postMessage({ type: 'refresh' });
        }

        function openDashboard() {
            vscode.postMessage({ type: 'openDashboard' });
        }
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
