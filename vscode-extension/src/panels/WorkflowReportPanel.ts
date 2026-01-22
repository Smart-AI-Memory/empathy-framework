/**
 * Workflow Report Panel - Unified webview for all workflow reports
 *
 * Displays dynamic reports for any workflow type including:
 * - Health checks
 * - Release prep
 * - Test coverage
 * - Security audits
 * - Performance audits
 * - And any future workflows
 *
 * Features:
 * - Runs workflow in background with progress notifications
 * - Dynamically formats output based on workflow type
 * - Common actions: Copy, Export, Re-run, Ask Claude
 * - Chart.js visualizations for metrics
 * - Proper error handling and status updates
 *
 * Copyright 2025 Smart AI Memory, LLC
 * Licensed under Fair Source 0.9
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

interface WorkflowReport {
    workflow: string;
    status: 'success' | 'running' | 'failed';
    timestamp: string;
    data: any;
    output: string;
    error?: string;
}

export class WorkflowReportPanel {
    public static currentPanel: WorkflowReportPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private _currentWorkflow: string = '';
    private _currentReport: WorkflowReport | null = null;

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, workflowName: string) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._currentWorkflow = workflowName;

        // Set panel title based on workflow
        this._panel.title = this._getWorkflowTitle(workflowName);

        // Set the webview's initial html content
        this._update();

        // Listen for when the panel is disposed
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Handle messages from the webview
        this._panel.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.type) {
                    case 'refresh':
                        await this._runWorkflow();
                        break;
                    case 'rerun':
                        await this._runWorkflow(message.input);
                        break;
                    case 'copyReport':
                        await this._copyReport();
                        break;
                    case 'exportJson':
                        await this._exportJson();
                        break;
                    case 'askClaude':
                        await this._askClaude(message.question);
                        break;
                    case 'openDashboard':
                        vscode.commands.executeCommand('empathy.dashboard');
                        break;
                    case 'openFile':
                        await this._openFile(message.filePath, message.line);
                        break;
                }
            },
            null,
            this._disposables
        );
    }

    public static createOrShow(extensionUri: vscode.Uri, workflowName: string, autoRun: boolean = true) {
        const column = vscode.ViewColumn.One;

        // If we already have a panel for this workflow, show it
        if (WorkflowReportPanel.currentPanel && WorkflowReportPanel.currentPanel._currentWorkflow === workflowName) {
            WorkflowReportPanel.currentPanel._panel.reveal(column);
            if (autoRun) {
                WorkflowReportPanel.currentPanel._runWorkflow();
            }
            return;
        }

        // Otherwise, create a new panel
        const panel = vscode.window.createWebviewPanel(
            'empathyWorkflowReport',
            'Workflow Report',
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    vscode.Uri.joinPath(extensionUri, 'webview'),
                ],
            }
        );

        WorkflowReportPanel.currentPanel = new WorkflowReportPanel(panel, extensionUri, workflowName);

        // Auto-run the workflow if requested
        if (autoRun) {
            WorkflowReportPanel.currentPanel._runWorkflow();
        }
    }

    public dispose() {
        WorkflowReportPanel.currentPanel = undefined;

        // Clean up resources
        this._panel.dispose();

        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) {
                x.dispose();
            }
        }
    }

    private _getWorkflowTitle(workflow: string): string {
        const titles: Record<string, string> = {
            'health-check': '🏥 Health Check Report (v4.0 CrewAI)',
            'release-prep': '🚀 Release Prep Report (v4.0 CrewAI)',
            'test-coverage-boost': '📊 Test Coverage Boost (v4.0 CrewAI)',
            'security-audit': '🔒 Security Audit Report',
            'perf-audit': '⚡ Performance Audit Report',
            'bug-predict': '🐛 Bug Prediction Report',
            'code-review': '👀 Code Review Report',
            'doc-gen': '📝 Documentation Report',
        };
        return titles[workflow] || `📄 ${workflow} Report`;
    }

    private async _runWorkflow(input?: string) {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }

        // Show in-progress state
        this._updateReport({
            workflow: this._currentWorkflow,
            status: 'running',
            timestamp: new Date().toISOString(),
            data: {},
            output: 'Running workflow...'
        });

        // Get configured python path
        const config = vscode.workspace.getConfiguration('empathy');
        const pythonPath = config.get<string>('pythonPath', 'python');

        // Build command args based on workflow type
        const args = this._buildWorkflowArgs(this._currentWorkflow, input);

        // Debug: Log the command being executed
        console.log('[WorkflowReportPanel] Running workflow:', this._currentWorkflow);
        console.log('[WorkflowReportPanel] Command args:', args);

        // Determine correct working directory
        // If we're in vscode-extension folder, use parent directory (Python project root)
        let cwd = workspaceFolder;
        if (workspaceFolder.endsWith('vscode-extension')) {
            const path = require('path');
            cwd = path.dirname(workspaceFolder);
            console.log('[WorkflowReportPanel] Running from parent directory:', cwd);
        }

        // Show progress notification
        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `Running ${this._getWorkflowTitle(this._currentWorkflow)}`,
            cancellable: false
        }, async (progress) => {
            progress.report({ message: 'Executing workflow...' });

            return new Promise<void>((resolve) => {
                cp.execFile(pythonPath, args, {
                    cwd: cwd,
                    maxBuffer: 1024 * 1024 * 10, // 10MB buffer
                    timeout: 300000 // 5 minute timeout
                }, async (error, stdout, stderr) => {
                    const output = stdout || stderr || '';

                    if (error) {
                        this._updateReport({
                            workflow: this._currentWorkflow,
                            status: 'failed',
                            timestamp: new Date().toISOString(),
                            data: {},
                            output: output,
                            error: error.message
                        });
                        vscode.window.showErrorMessage(`Workflow failed: ${error.message}`);
                    } else {
                        // Try to parse JSON output
                        const data = this._parseWorkflowOutput(output);

                        this._updateReport({
                            workflow: this._currentWorkflow,
                            status: 'success',
                            timestamp: new Date().toISOString(),
                            data: data,
                            output: output
                        });

                        vscode.window.showInformationMessage(`✅ ${this._getWorkflowTitle(this._currentWorkflow)} complete`);
                    }

                    resolve();
                });
            });
        });
    }

    private _buildWorkflowArgs(workflow: string, input?: string): string[] {
        // v4.0: Orchestrated workflows use 'orchestrate' subcommand with JSON output
        if (workflow === 'orchestrated-health-check') {
            const baseArgs = ['-m', 'empathy_os.cli', 'orchestrate', 'health-check', '--mode', 'daily', '--json'];
            return baseArgs;
        } else if (workflow === 'orchestrated-release-prep') {
            // v4.6.3: Use 'empathy' CLI directly
            const baseArgs = ['orchestrate', 'release-prep', '--path', '.', '--json'];
            return baseArgs;
        } else {
            // v4.6.3: Other workflows use 'empathy workflow run' command
            const baseArgs = ['workflow', 'run', workflow];

            // Add input if provided
            if (input) {
                baseArgs.push('--input', input);
            }

            return baseArgs;
        }
    }

    private _parseWorkflowOutput(output: string): any {
        // Try to extract JSON from output
        try {
            // Look for JSON patterns in output (orchestrated workflows now use --json flag)
            const jsonMatch = output.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                const parsed = JSON.parse(jsonMatch[0]);
                // Successfully parsed JSON - return it
                return parsed;
            }
        } catch (e) {
            // If parsing fails, fall through to text parsing
        }

        // Fallback: Parse common output patterns (for legacy workflows)
        return this._parseTextOutput(output);
    }

    private _parseTextOutput(output: string): any {
        const data: any = {
            raw_output: output
        };

        // Extract health score (multiple formats)
        // Match any characters (including emojis) before the score
        const healthScoreMatch = output.match(/(?:Overall Health|Health Score):\s*[^\d]*(\d+\.?\d*)\s*\/\s*100/i);
        if (healthScoreMatch) {
            data.health_score = parseFloat(healthScoreMatch[1]);
        }

        // Extract grade
        const gradeMatch = output.match(/Grade:\s*([A-F])/i);
        if (gradeMatch) {
            data.grade = gradeMatch[1];
        }

        // Extract cost
        const costMatch = output.match(/Cost:\s*\$(\d+\.?\d*)/i);
        if (costMatch) {
            data.cost = parseFloat(costMatch[1]);
        }

        // Extract duration
        const durationMatch = output.match(/Duration:\s*(\d+)ms/i);
        if (durationMatch) {
            data.duration_ms = parseInt(durationMatch[1]);
        }

        // Extract coverage
        const coverageMatch = output.match(/Coverage:\s*(\d+\.?\d*)%/i);
        if (coverageMatch) {
            data.coverage = parseFloat(coverageMatch[1]);
        }

        // Extract issues count
        const issuesMatch = output.match(/(\d+)\s+issues?\s+found/i);
        if (issuesMatch) {
            data.issues_count = parseInt(issuesMatch[1]);
        }

        return data;
    }

    private _updateReport(report: WorkflowReport) {
        this._currentReport = report;
        this._panel.webview.postMessage({
            type: 'reportUpdate',
            data: report
        });
    }

    private async _copyReport() {
        if (!this._currentReport) {
            return;
        }

        await vscode.env.clipboard.writeText(this._currentReport.output);
        vscode.window.showInformationMessage('Report copied to clipboard');
    }

    private async _exportJson() {
        if (!this._currentReport) {
            return;
        }

        const uri = await vscode.window.showSaveDialog({
            filters: { 'JSON': ['json'] },
            defaultUri: vscode.Uri.file(`${this._currentWorkflow}-report.json`)
        });

        if (uri) {
            fs.writeFileSync(uri.fsPath, JSON.stringify(this._currentReport, null, 2));
            vscode.window.showInformationMessage(`Report exported to ${uri.fsPath}`);
        }
    }

    private async _askClaude(question: string) {
        if (!this._currentReport) {
            return;
        }

        const prompt = `Based on this ${this._currentWorkflow} report:\n\n${this._currentReport.output}\n\nQuestion: ${question}`;

        // Open Claude in new editor with question
        const doc = await vscode.workspace.openTextDocument({
            content: prompt,
            language: 'markdown'
        });
        await vscode.window.showTextDocument(doc);
    }

    private async _openFile(filePath: string, line?: number) {
        const uri = vscode.Uri.file(filePath);
        const doc = await vscode.workspace.openTextDocument(uri);
        const editor = await vscode.window.showTextDocument(doc);

        if (line !== undefined && line > 0) {
            const pos = new vscode.Position(line - 1, 0);
            editor.selection = new vscode.Selection(pos, pos);
            editor.revealRange(new vscode.Range(pos, pos));
        }
    }

    private _update() {
        this._panel.webview.html = this._getHtmlForWebview();
    }

    private _getHtmlForWebview(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${this._getWorkflowTitle(this._currentWorkflow)}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.3.0/dist/chart.umd.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: var(--vscode-font-family);
            color: var(--vscode-foreground);
            background: var(--vscode-editor-background);
            padding: 20px;
            line-height: 1.6;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }

        .title {
            font-size: 24px;
            font-weight: 600;
        }

        .actions {
            display: flex;
            gap: 8px;
        }

        button {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            transition: background 0.2s;
        }

        button:hover {
            background: var(--vscode-button-hoverBackground);
        }

        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 12px;
        }

        .status-running {
            background: #ffa500;
            color: white;
        }

        .status-success {
            background: #28a745;
            color: white;
        }

        .status-failed {
            background: #dc3545;
            color: white;
        }

        .report-container {
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: var(--vscode-descriptionForeground);
        }

        .spinner {
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 4px solid var(--vscode-panel-border);
            border-top-color: var(--vscode-button-background);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin: 20px 0;
        }

        .metric-card {
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 8px;
            padding: 16px;
        }

        .metric-label {
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
            margin-bottom: 4px;
        }

        .metric-value {
            font-size: 24px;
            font-weight: 600;
        }

        .section {
            margin: 24px 0;
        }

        .section-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }

        .issue-list {
            list-style: none;
        }

        .issue-item {
            padding: 12px;
            margin-bottom: 8px;
            background: var(--vscode-editor-background);
            border-left: 3px solid var(--vscode-panel-border);
            border-radius: 4px;
        }

        .issue-item.critical {
            border-left-color: #dc3545;
        }

        .issue-item.high {
            border-left-color: #ffa500;
        }

        .issue-item.medium {
            border-left-color: #ffc107;
        }

        .issue-item.low {
            border-left-color: #28a745;
        }

        .file-link {
            color: var(--vscode-textLink-foreground);
            cursor: pointer;
            text-decoration: none;
        }

        .file-link:hover {
            text-decoration: underline;
        }

        pre {
            background: var(--vscode-textCodeBlock-background);
            padding: 12px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 12px;
        }

        .chart-container {
            max-width: 400px;
            margin: 20px auto;
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <span class="title" id="title">${this._getWorkflowTitle(this._currentWorkflow)}</span>
            <span class="status-badge status-running" id="status">Initializing...</span>
        </div>
        <div class="actions">
            <button onclick="refresh()">🔄 Refresh</button>
            <button onclick="copyReport()">📋 Copy</button>
            <button onclick="exportJson()">💾 Export</button>
            <button onclick="openDashboard()">🏠 Dashboard</button>
        </div>
    </div>

    <div id="content">
        <div class="loading">
            <div class="spinner"></div>
            <p style="margin-top: 16px;">Initializing report...</p>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentReport = null;

        // Listen for messages from extension
        window.addEventListener('message', event => {
            const message = event.data;

            if (message.type === 'reportUpdate') {
                currentReport = message.data;
                updateUI(message.data);
            }
        });

        function updateUI(report) {
            const statusEl = document.getElementById('status');
            const contentEl = document.getElementById('content');

            // Update status badge
            statusEl.className = 'status-badge status-' + report.status;
            statusEl.textContent = report.status === 'running' ? 'Running...' :
                                  report.status === 'success' ? 'Complete' : 'Failed';

            // Update content based on workflow type and status
            if (report.status === 'running') {
                contentEl.innerHTML = \`
                    <div class="loading">
                        <div class="spinner"></div>
                        <p style="margin-top: 16px;">Running workflow...</p>
                    </div>
                \`;
            } else if (report.status === 'failed') {
                contentEl.innerHTML = \`
                    <div class="report-container">
                        <h2 style="color: #dc3545;">❌ Workflow Failed</h2>
                        <p style="margin-top: 12px;">\${report.error || 'Unknown error'}</p>
                        <pre style="margin-top: 12px;">\${escapeHtml(report.output)}</pre>
                    </div>
                \`;
            } else {
                // Success - render formatted report
                contentEl.innerHTML = renderReport(report);
            }
        }

        function renderReport(report) {
            const workflow = report.workflow;

            // Dispatch to workflow-specific formatter
            if (workflow.includes('health-check')) {
                return formatHealthCheck(report);
            } else if (workflow.includes('release-prep')) {
                return formatReleasePrep(report);
            } else if (workflow.includes('test-coverage')) {
                return formatTestCoverage(report);
            } else if (workflow.includes('security-audit')) {
                return formatSecurityAudit(report);
            } else {
                // Generic formatter for unknown workflows
                return formatGeneric(report);
            }
        }

        function formatHealthCheck(report) {
            const data = report.data;
            const healthScore = Math.round(data.overall_health_score || 0);
            const grade = data.grade || 'F';
            const categories = data.category_scores || [];
            const issues = data.issues || [];
            const recommendations = data.recommendations || [];
            const executionTime = (data.execution_time || 0).toFixed(2);
            const agentsExecuted = data.agents_executed || 0;

            // Determine health score color
            const scoreColor = healthScore >= 80 ? '#28a745' : healthScore >= 60 ? '#ffc107' : '#dc3545';
            const gradeEmoji = healthScore >= 80 ? '✅' : healthScore >= 60 ? '⚠️' : '❌';

            // Build categories HTML
            const categoriesHtml = categories.map(cat => {
                const catScore = Math.round(cat.score || 0);
                const catColor = cat.passed ? '#28a745' : '#dc3545';
                const catIcon = cat.passed ? '✅' : '❌';
                const barWidth = Math.max(0, Math.min(100, catScore));

                return \`
                    <div style="margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                            <span style="font-weight: 600; color: #e0e0e0;">\${catIcon} \${cat.name}</span>
                            <span style="color: \${catColor}; font-weight: 600;">\${catScore}/100</span>
                        </div>
                        <div style="background: #2d2d2d; height: 8px; border-radius: 4px; overflow: hidden;">
                            <div style="background: \${catColor}; height: 100%; width: \${barWidth}%;"></div>
                        </div>
                        \${cat.issues && cat.issues.length > 0 ? \`
                            <div style="margin-top: 4px; font-size: 12px; color: #bbb;">
                                \${cat.issues.map(issue => \`• \${issue}\`).join('<br>')}
                            </div>
                        \` : ''}
                    </div>
                \`;
            }).join('');

            return \`
                <div class="metric-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px;">
                    <div class="metric-card" style="background: #1e1e1e; padding: 16px; border-radius: 8px; border: 1px solid #333;">
                        <div class="metric-label" style="color: #888; font-size: 12px; margin-bottom: 8px;">Health Score</div>
                        <div class="metric-value" style="color: \${scoreColor}; font-size: 32px; font-weight: 700;">
                            \${gradeEmoji} \${healthScore}<span style="font-size: 18px;">/100</span>
                        </div>
                        <div style="color: #888; font-size: 14px; margin-top: 4px;">Grade: \${grade}</div>
                    </div>
                    <div class="metric-card" style="background: #1e1e1e; padding: 16px; border-radius: 8px; border: 1px solid #333;">
                        <div class="metric-label" style="color: #888; font-size: 12px; margin-bottom: 8px;">Issues Found</div>
                        <div class="metric-value" style="color: \${issues.length > 0 ? '#dc3545' : '#28a745'}; font-size: 32px; font-weight: 700;">
                            \${issues.length}
                        </div>
                        <div style="color: #888; font-size: 14px; margin-top: 4px;">\${issues.length === 0 ? 'No issues' : 'needs attention'}</div>
                    </div>
                    <div class="metric-card" style="background: #1e1e1e; padding: 16px; border-radius: 8px; border: 1px solid #333;">
                        <div class="metric-label" style="color: #888; font-size: 12px; margin-bottom: 8px;">Execution Time</div>
                        <div class="metric-value" style="color: #007acc; font-size: 32px; font-weight: 700;">
                            \${executionTime}<span style="font-size: 18px;">s</span>
                        </div>
                        <div style="color: #888; font-size: 14px; margin-top: 4px;">\${agentsExecuted} agents</div>
                    </div>
                </div>

                <div class="section" style="background: #1e1e1e; padding: 16px; border-radius: 8px; border: 1px solid #333; margin-bottom: 16px;">
                    <div class="section-title" style="font-size: 14px; font-weight: 600; margin-bottom: 12px; color: #fff;">📊 Category Breakdown</div>
                    \${categoriesHtml}
                </div>

                \${recommendations.length > 0 ? \`
                    <div class="section" style="background: #1e1e1e; padding: 16px; border-radius: 8px; border: 1px solid #333; margin-bottom: 16px;">
                        <div class="section-title" style="font-size: 14px; font-weight: 600; margin-bottom: 12px; color: #fff;">💡 Recommendations</div>
                        <div style="font-size: 13px; line-height: 1.6; color: #d0d0d0;">
                            \${recommendations.map(rec => \`<div style="margin-bottom: 8px;">\${escapeHtml(rec)}</div>\`).join('')}
                        </div>
                    </div>
                \` : ''}

                <div class="section">
                    <button onclick="askClaude('How can I improve the health score from \${healthScore} to 90+?')" style="background: #007acc; color: white; border: none; padding: 10px 16px; border-radius: 6px; cursor: pointer; font-size: 13px;">
                        🤖 Ask Claude for Help
                    </button>
                </div>
            \`;
        }

        function formatReleasePrep(report) {
            const output = report.output;
            const isReady = output.includes('READY FOR RELEASE') || output.includes('Release Ready: true');

            return \`
                <div class="report-container">
                    <h2 style="color: \${isReady ? '#28a745' : '#ffa500'}">
                        \${isReady ? '✅ Ready for Release' : '⚠️ Release Blockers Found'}
                    </h2>
                </div>

                <div class="section">
                    <div class="section-title">Validation Results</div>
                    <pre>\${escapeHtml(output)}</pre>
                </div>

                <div class="section">
                    <button onclick="askClaude('What are the release blockers and how do I fix them?')">🤖 Ask Claude for Help</button>
                </div>
            \`;
        }

        function formatTestCoverage(report) {
            const data = report.data;
            const coverage = data.coverage || 0;

            return \`
                <div class="metric-grid">
                    <div class="metric-card">
                        <div class="metric-label">Test Coverage</div>
                        <div class="metric-value">\${coverage}%</div>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">Coverage Report</div>
                    <pre>\${escapeHtml(report.output)}</pre>
                </div>

                <div class="section">
                    <button onclick="askClaude('How can I improve test coverage?')">🤖 Ask Claude for Help</button>
                </div>
            \`;
        }

        function formatSecurityAudit(report) {
            return formatGeneric(report);
        }

        function formatGeneric(report) {
            return \`
                <div class="section">
                    <div class="section-title">Report Output</div>
                    <pre>\${escapeHtml(report.output)}</pre>
                </div>

                <div class="section">
                    <button onclick="askClaude('Explain this report to me')">🤖 Ask Claude for Help</button>
                </div>
            \`;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function refresh() {
            vscode.postMessage({ type: 'refresh' });
        }

        function copyReport() {
            vscode.postMessage({ type: 'copyReport' });
        }

        function exportJson() {
            vscode.postMessage({ type: 'exportJson' });
        }

        function openDashboard() {
            vscode.postMessage({ type: 'openDashboard' });
        }

        function askClaude(question) {
            vscode.postMessage({ type: 'askClaude', question });
        }
    </script>
</body>
</html>`;
    }
}
