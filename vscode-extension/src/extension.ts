/**
 * Empathy Framework VS Code Extension
 *
 * Provides integration with Empathy Framework including:
 * - Status bar showing health score and cost savings
 * - Command palette for all CLI commands
 * - Sidebar with pattern browser
 * - Inline diagnostics from inspection
 * - Quick fix actions and auto-scan on save
 *
 * Copyright 2025 Smart-AI-Memory
 * Licensed under Fair Source License 0.9
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { PowerPanel } from './panels/PowerPanel';
import { HealthPanel } from './panels/HealthPanel';
import { CostsPanel } from './panels/CostsPanel';
import { WorkflowHistoryPanel } from './panels/WorkflowHistoryPanel';
import { TelemetryPanel } from './panels/TelemetryPanel';
import { EmpathyDashboardProvider } from './panels/EmpathyDashboardPanel';
import { CoveragePanel } from './panels/CoveragePanel';
import { WorkflowFactoryPanel } from './panels/WorkflowFactoryPanel';
import { WorkflowReportPanel } from './panels/WorkflowReportPanel';
import { MemoryPanelProvider } from './panels/MemoryPanelProvider';
// REMOVED in v3.5.5: Refactor Advisor panel - kept for future use
// import { RefactorAdvisorPanel } from './panels/RefactorAdvisorPanel';
import { ResearchSynthesisPanel } from './panels/ResearchSynthesisPanel';
import { InitializeWizardPanel } from './panels/InitializeWizardPanel';
import { MorningBriefingPanel } from './panels/MorningBriefingPanel';
// REMOVED in v3.5.5: Test Generator panel - kept for future use
// import { TestGeneratorPanel } from './panels/TestGeneratorPanel';
// HIDDEN in v3.5.5: Workflow Wizard panel - temporarily hidden
// import { WorkflowWizardPanel } from './panels/WorkflowWizardPanel';
import { DocAnalysisPanel } from './panels/DocAnalysisPanel';
import { initializeProject, showWelcomeIfNeeded as showInitializeWelcome } from './commands/initializeProject';
import { registerMetaWorkflowCommands } from './commands/metaWorkflowCommands';

// Status bar item
let statusBarItem: vscode.StatusBarItem;

// Telemetry status bar item
let telemetryStatusBarItem: vscode.StatusBarItem;

// Health provider (used for diagnostics)
let healthProvider: HealthTreeProvider;

// Extension path (for accessing bundled scripts)
let extensionPath: string;

// Refresh timer
let refreshTimer: NodeJS.Timeout | undefined;

// Health scan timer (regenerates health.json periodically)
let healthScanTimer: NodeJS.Timeout | undefined;

// Diagnostics collection for Problem Panel (Feature F)
let diagnosticCollection: vscode.DiagnosticCollection;

// Security diagnostics collection (separate from lint issues)
let securityDiagnosticCollection: vscode.DiagnosticCollection;

// File watcher for auto-scan (Feature E)
let fileWatcher: vscode.FileSystemWatcher | undefined;

// File watcher for security findings
let securityFindingsWatcher: vscode.FileSystemWatcher | undefined;

/**
 * Extension activation
 */
export function activate(context: vscode.ExtensionContext) {
    console.log('Empathy Framework extension activated');

    // Store extension path for accessing bundled scripts
    extensionPath = context.extensionPath;

    // Create status bar
    statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    statusBarItem.command = 'empathy.status';
    context.subscriptions.push(statusBarItem);

    // Create telemetry status bar button
    telemetryStatusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        99
    );
    telemetryStatusBarItem.text = '$(dashboard) Telemetry';
    telemetryStatusBarItem.tooltip = 'Open LLM Telemetry Dashboard';
    telemetryStatusBarItem.command = 'empathy.openTelemetry';
    telemetryStatusBarItem.show();
    context.subscriptions.push(telemetryStatusBarItem);

    // Create diagnostics collection (Feature F)
    diagnosticCollection = vscode.languages.createDiagnosticCollection('empathy');
    context.subscriptions.push(diagnosticCollection);

    // Create security diagnostics collection (separate from lint issues)
    securityDiagnosticCollection = vscode.languages.createDiagnosticCollection('empathy-security');
    context.subscriptions.push(securityDiagnosticCollection);

    // Create health provider (for diagnostics support)
    healthProvider = new HealthTreeProvider(diagnosticCollection, securityDiagnosticCollection);

    // Register dashboard webview provider (with context for persistence)
    const dashboardProvider = new EmpathyDashboardProvider(context.extensionUri, context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            EmpathyDashboardProvider.viewType,
            dashboardProvider
        )
    );

    // Memory panel (Beta) - requires backend server for full functionality
    const memoryProvider = new MemoryPanelProvider(context.extensionUri, context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            MemoryPanelProvider.viewType,
            memoryProvider,
            {
                webviewOptions: {
                    retainContextWhenHidden: true
                }
            }
        )
    );

    // Workflow Factory panel opens in editor area (created on demand via command)

    // REMOVED in v3.5.5: Refactor Advisor panel - kept for future use
    // const refactorAdvisorProvider = new RefactorAdvisorPanel(context.extensionUri, context);
    // context.subscriptions.push(
    //     vscode.window.registerWebviewViewProvider(
    //         RefactorAdvisorPanel.viewType,
    //         refactorAdvisorProvider,
    //         {
    //             webviewOptions: {
    //                 retainContextWhenHidden: true
    //             }
    //         }
    //     )
    // );

    // Research Synthesis panel - Multi-document research and synthesis
    const researchSynthesisProvider = new ResearchSynthesisPanel(context.extensionUri, context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            ResearchSynthesisPanel.viewType,
            researchSynthesisProvider,
            {
                webviewOptions: {
                    retainContextWhenHidden: true
                }
            }
        )
    );

    // REMOVED in v3.5.5: Test Generator panel - kept for future use
    // Opens in main editor area (not sidebar) using createOrShow pattern
    // context.subscriptions.push(
    //     vscode.commands.registerCommand('empathy.openTestGenerator', () => {
    //         TestGeneratorPanel.createOrShow(context.extensionUri);
    //     })
    // );

    // HIDDEN in v3.5.5: Workflow Wizard panel - temporarily hidden, kept for future use
    // const workflowWizardProvider = new WorkflowWizardPanel(context.extensionUri, context);
    // context.subscriptions.push(
    //     vscode.window.registerWebviewViewProvider(
    //         WorkflowWizardPanel.viewType,
    //         workflowWizardProvider,
    //         {
    //             webviewOptions: {
    //                 retainContextWhenHidden: true
    //             }
    //         }
    //     )
    // );

    // Register commands - existing
    const commands = [
        { name: 'empathy.morning', handler: cmdMorning },
        { name: 'empathy.ship', handler: cmdShip },
        { name: 'empathy.fixAll', handler: cmdFixAll },
        { name: 'empathy.learn', handler: cmdLearn },
        { name: 'empathy.costs', handler: cmdCosts },
        { name: 'empathy.dashboard', handler: cmdDashboard },
        { name: 'empathy.syncClaude', handler: cmdSyncClaude },
        { name: 'empathy.status', handler: cmdStatus },
        // New commands for Health view actions (Features A, B, C, D)
        { name: 'empathy.refreshHealth', handler: cmdRefreshHealth },
        { name: 'empathy.runScan', handler: cmdRunScan },
        { name: 'empathy.runSecurityScan', handler: cmdRunSecurityScan },
        { name: 'empathy.fixLint', handler: cmdFixLint },
        { name: 'empathy.fixFormat', handler: cmdFixFormat },
        { name: 'empathy.runTests', handler: cmdRunTests },
        { name: 'empathy.viewDetails', handler: cmdViewDetails },
        { name: 'empathy.openFile', handler: cmdOpenFile },
        { name: 'empathy.ignoreIssue', handler: cmdIgnoreIssue },
        { name: 'empathy.openWebDashboard', handler: cmdOpenWebDashboard },
        // Memory commands (Beta)
        { name: 'empathy.memory.showPanel', handler: () => vscode.commands.executeCommand('empathy-memory.focus') },
        { name: 'empathy.memory.refreshStatus', handler: () => { memoryProvider.refresh(); vscode.window.showInformationMessage('Memory status refreshed'); } },
        // Initialize wizard (accepts optional { force: true } to skip "already initialized" check)
        { name: 'empathy.initializeProject', handler: (options?: { force?: boolean }) => initializeProject(context, options) },
        // Navigation command
        { name: 'empathy.goToLocation', handler: async (location: { file: string; line: number; column?: number }) => {
            const uri = vscode.Uri.file(location.file);
            const doc = await vscode.workspace.openTextDocument(uri);
            const editor = await vscode.window.showTextDocument(doc);
            const position = new vscode.Position(location.line - 1, (location.column || 1) - 1);
            editor.selection = new vscode.Selection(position, position);
            editor.revealRange(new vscode.Range(position, position));
        }},
        // Workflow execution command
        { name: 'empathy.runWorkflow', handler: async (workflowName: string, input?: any) => {
            const terminal = vscode.window.createTerminal('Empathy Workflow');
            terminal.show();
            if (input) {
                terminal.sendText(`empathy workflow run ${workflowName} --input '${JSON.stringify(input)}'`);
            } else {
                terminal.sendText(`empathy workflow run ${workflowName}`);
            }
        }},
        // Agent Factory command (distinct from wizards/workflows)
        { name: 'empathy.agentFactory', handler: async () => {
            vscode.window.showInformationMessage('Agent Factory: Agent creation tools (separate from wizards and workflows)');
        }},
        // Keyboard layout command
        { name: 'empathy.applyKeyboardLayout', handler: async () => {
            await vscode.commands.executeCommand('workbench.action.openGlobalKeybindings');
        }},
        // Wizard Factory commands (12x faster wizard creation)
        { name: 'empathy.wizard.create', handler: async () => {
            const wizardName = await vscode.window.showInputBox({
                prompt: 'Enter wizard name (snake_case)',
                placeHolder: 'patient_intake',
                validateInput: (value) => {
                    if (!value) return 'Wizard name is required';
                    if (!/^[a-z_][a-z0-9_]*$/.test(value)) return 'Use snake_case (lowercase with underscores)';
                    return null;
                }
            });
            if (!wizardName) return;

            const domain = await vscode.window.showQuickPick(
                ['healthcare', 'finance', 'software', 'legal', 'education', 'other'],
                { placeHolder: 'Select domain' }
            );
            if (!domain) return;

            const wizardType = await vscode.window.showQuickPick(
                ['domain', 'coach', 'ai'],
                { placeHolder: 'Select wizard type (default: domain)' }
            );
            if (!wizardType) return;

            const terminal = vscode.window.createTerminal('Wizard Factory');
            terminal.show();
            terminal.sendText(`empathy wizard create ${wizardName} --domain ${domain} --type ${wizardType}`);
            vscode.window.showInformationMessage(`Creating wizard: ${wizardName} (${domain})`);
        }},
        { name: 'empathy.wizard.listPatterns', handler: async () => {
            const terminal = vscode.window.createTerminal('Wizard Patterns');
            terminal.show();
            terminal.sendText('empathy wizard list-patterns');
        }},
        { name: 'empathy.wizard.generateTests', handler: async () => {
            const wizardId = await vscode.window.showInputBox({
                prompt: 'Enter wizard ID to generate tests for',
                placeHolder: 'patient_intake'
            });
            if (!wizardId) return;

            const patterns = await vscode.window.showInputBox({
                prompt: 'Enter comma-separated pattern IDs',
                placeHolder: 'linear_flow,approval,structured_fields',
                validateInput: (value) => value ? null : 'Patterns are required'
            });
            if (!patterns) return;

            const terminal = vscode.window.createTerminal('Test Generator');
            terminal.show();
            terminal.sendText(`empathy wizard generate-tests ${wizardId} --patterns ${patterns}`);
            vscode.window.showInformationMessage(`Generating tests for: ${wizardId}`);
        }},
        { name: 'empathy.wizard.analyze', handler: async () => {
            const wizardId = await vscode.window.showInputBox({
                prompt: 'Enter wizard ID to analyze',
                placeHolder: 'patient_intake'
            });
            if (!wizardId) return;

            const patterns = await vscode.window.showInputBox({
                prompt: 'Enter comma-separated pattern IDs',
                placeHolder: 'linear_flow,approval,structured_fields',
                validateInput: (value) => value ? null : 'Patterns are required'
            });
            if (!patterns) return;

            const terminal = vscode.window.createTerminal('Wizard Risk Analysis');
            terminal.show();
            terminal.sendText(`empathy wizard analyze ${wizardId} --patterns ${patterns}`);
            vscode.window.showInformationMessage(`Analyzing risk for: ${wizardId}`);
        }},
        // Workflow Factory commands - opens visual webview panel
        { name: 'empathy.workflow.create', handler: async () => {
            // Open the Workflow Factory webview panel in editor area
            WorkflowFactoryPanel.createOrShow(context.extensionUri);
        }},
        { name: 'empathy.workflow.listPatterns', handler: async () => {
            const terminal = vscode.window.createTerminal('Workflow Patterns');
            terminal.show();
            terminal.sendText('empathy workflow list-patterns');
        }},
        { name: 'empathy.workflow.recommend', handler: async () => {
            const workflowType = await vscode.window.showQuickPick(
                ['code-analysis', 'multi-agent', 'data-processing', 'custom'],
                {
                    placeHolder: 'Select workflow type to get pattern recommendations',
                    title: 'Workflow Pattern Recommendations'
                }
            );
            if (!workflowType) return;

            const terminal = vscode.window.createTerminal('Workflow Recommendations');
            terminal.show();
            terminal.sendText(`empathy workflow recommend ${workflowType}`);
        }},
        // REMOVED in v3.5.5: Test Generator wizard
        // { name: 'empathy.testGenerator.show', handler: () => vscode.commands.executeCommand('empathy.openTestGenerator') },
        // HIDDEN in v3.5.5: Workflow Wizard (temporarily disabled - panel is hidden)
        // { name: 'empathy.workflowWizard.show', handler: () => vscode.commands.executeCommand('workflow-wizard.focus') },
    ];

    for (const cmd of commands) {
        context.subscriptions.push(
            vscode.commands.registerCommand(cmd.name, cmd.handler)
        );
    }

    // Register Power Panel command (needs extensionUri)
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.openPowerPanel', () => {
            PowerPanel.createOrShow(context.extensionUri);
        })
    );

    // Register Health Panel command
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.openHealthPanel', () => {
            HealthPanel.createOrShow(context.extensionUri);
        })
    );

    // Register Coverage Panel command (v4.0 Meta-Orchestration)
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.openCoveragePanel', () => {
            CoveragePanel.createOrShow(context.extensionUri);
        })
    );

    // Register Workflow Report Panel commands (Unified report panel for all workflows)
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.openWorkflowReport', (workflowName: string) => {
            WorkflowReportPanel.createOrShow(context.extensionUri, workflowName, true);
        })
    );

    // Specific workflow report commands (v4.0 - use CrewAI workflow names)
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.runHealthCheckReport', () => {
            WorkflowReportPanel.createOrShow(context.extensionUri, 'health-check', true);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.runReleasePrepReport', () => {
            WorkflowReportPanel.createOrShow(context.extensionUri, 'release-prep', true);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.runTestCoverageReport', () => {
            WorkflowReportPanel.createOrShow(context.extensionUri, 'test-coverage-boost', true);
        })
    );

    // Register Costs Panel command
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.openCostsPanel', () => {
            CostsPanel.createOrShow(context.extensionUri);
        })
    );

    // Register Workflow History Panel command
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.openWorkflowHistory', () => {
            WorkflowHistoryPanel.createOrShow(context.extensionUri);
        })
    );

    // Register Telemetry Panel command
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.openTelemetry', () => {
            TelemetryPanel.createOrShow(context.extensionUri);
        })
    );

    // Register command to focus sidebar dashboard
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.focusSidebarDashboard', async () => {
            // First, reveal the Empathy view container in the activity bar
            await vscode.commands.executeCommand('workbench.view.extension.empathy-explorer');
            // Then focus the specific dashboard view
            await vscode.commands.executeCommand('empathy-dashboard.focus');
        })
    );

    // Register Documentation Analysis Panel command
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.openDocAnalysis', () => {
            DocAnalysisPanel.createOrShow(context.extensionUri);
        })
    );

    // Register command to open workflow reports in editor
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.openReportInEditor', async (args: { workflowName: string; output: string; input?: string }) => {
            const workflowNames: Record<string, string> = {
                'code-review': 'Code Review',
                'bug-predict': 'Bug Prediction',
                'security-audit': 'Security Audit',
                'perf-audit': 'Performance Audit',
                'refactor-plan': 'Refactoring Plan',
                'health-check': 'Health Check',
                'pr-review': 'PR Review',
                'pro-review': 'Code Analysis',
            };

            const displayName = workflowNames[args.workflowName] || args.workflowName;
            const timestamp = new Date().toLocaleString();

            let content = `# ${displayName} Report\n\n`;
            content += `**Generated:** ${timestamp}\n`;
            if (args.input) {
                content += `**Target:** ${args.input}\n`;
            }
            content += `\n---\n\n`;
            content += args.output;
            content += `\n\n---\n*Generated by Empathy Framework*`;

            const doc = await vscode.workspace.openTextDocument({
                content,
                language: 'markdown',
            });
            await vscode.window.showTextDocument(doc, {
                viewColumn: vscode.ViewColumn.One,
                preview: false,
                preserveFocus: false
            });
        })
    );

    // Register quick workflow command - allows running any workflow directly with WebView output
    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.runWorkflowQuick', async (workflowArg?: string) => {
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
            if (!workspaceFolder) {
                vscode.window.showErrorMessage('No workspace folder open');
                return;
            }

            const workflows = [
                { label: 'Code Review', value: 'code-review', icon: '$(eye)', type: 'file' },
                { label: 'Bug Prediction', value: 'bug-predict', icon: '$(bug)', type: 'folder' },
                { label: 'Security Audit', value: 'security-audit', icon: '$(shield)', type: 'folder' },
                { label: 'Performance Audit', value: 'perf-audit', icon: '$(dashboard)', type: 'folder' },
                { label: 'Refactoring Plan', value: 'refactor-plan', icon: '$(tools)', type: 'folder' },
                { label: 'Health Check', value: 'health-check', icon: '$(heart)', type: 'folder' },
                { label: 'PR Review', value: 'pr-review', icon: '$(git-pull-request)', type: 'folder' },
                { label: 'Code Analysis', value: 'pro-review', icon: '$(code)', type: 'file' },
                { label: 'Test Generation', value: 'test-gen', icon: '$(beaker)', type: 'folder' },
                { label: 'Dependency Check', value: 'dependency-check', icon: '$(package)', type: 'folder' },
                { label: 'Documentation', value: 'document-gen', icon: '$(book)', type: 'folder' },
                { label: 'Research Synthesis', value: 'research-synthesis', icon: '$(search)', type: 'folder' },
                { label: 'Release Prep', value: 'release-prep', icon: '$(rocket)', type: 'folder' },
            ];

            // Select workflow
            let selectedWorkflow: typeof workflows[0] | undefined;
            if (workflowArg) {
                selectedWorkflow = workflows.find(w => w.value === workflowArg);
            }
            if (!selectedWorkflow) {
                const pick = await vscode.window.showQuickPick(
                    workflows.map(w => ({ ...w, label: `${w.icon} ${w.label}`, description: w.value })),
                    { placeHolder: 'Select a workflow to run', ignoreFocusOut: true }
                );
                if (!pick) { return; }
                selectedWorkflow = pick;
            }

            // Select target
            let targetPath = '.';
            if (selectedWorkflow.type === 'folder') {
                const folderResult = await vscode.window.showQuickPick([
                    { label: '$(folder) Entire Project', path: '.' },
                    { label: '$(folder-opened) Select Folder...', path: '__browse__' }
                ], { placeHolder: 'Select scope', ignoreFocusOut: true });

                if (!folderResult) { return; }
                if (folderResult.path === '__browse__') {
                    const uri = await vscode.window.showOpenDialog({
                        canSelectFiles: false, canSelectFolders: true, canSelectMany: false,
                        defaultUri: vscode.Uri.file(workspaceFolder)
                    });
                    if (!uri?.[0]) { return; }
                    targetPath = uri[0].fsPath;
                }
            } else {
                const fileResult = await vscode.window.showQuickPick([
                    { label: '$(file) Current File', path: '__active__' },
                    { label: '$(folder) Entire Project', path: '.' },
                    { label: '$(file-add) Select File...', path: '__browse__' }
                ], { placeHolder: 'Select scope', ignoreFocusOut: true });

                if (!fileResult) { return; }
                if (fileResult.path === '__active__') {
                    targetPath = vscode.window.activeTextEditor?.document.uri.fsPath || '.';
                } else if (fileResult.path === '__browse__') {
                    const uri = await vscode.window.showOpenDialog({
                        canSelectFiles: true, canSelectFolders: false, canSelectMany: false,
                        defaultUri: vscode.Uri.file(workspaceFolder)
                    });
                    if (!uri?.[0]) { return; }
                    targetPath = uri[0].fsPath;
                }
            }

            // Create WebView with loading spinner
            const panel = vscode.window.createWebviewPanel(
                'empathyWorkflow',
                `${selectedWorkflow.label} Report`,
                vscode.ViewColumn.One,
                { enableScripts: true }
            );

            panel.webview.html = getLoadingHtml(selectedWorkflow.label, targetPath);

            // Store last output for copy functionality
            let lastOutput = '';

            // Handle messages from WebView
            panel.webview.onDidReceiveMessage(async (message) => {
                console.log('[EmpathyWorkflow] Received message:', message);
                switch (message.command) {
                    case 'copy':
                        await vscode.env.clipboard.writeText(lastOutput);
                        vscode.window.showInformationMessage('Report copied to clipboard');
                        break;
                    case 'runAgain':
                        console.log('[EmpathyWorkflow] Running workflow again');
                        panel.webview.html = getLoadingHtml(selectedWorkflow!.label, targetPath);
                        runWorkflow();
                        break;
                    case 'close':
                        panel.dispose();
                        break;
                }
            });

            // Function to run the workflow
            const runWorkflow = () => {
                // v4.6.3: Use 'empathy' CLI directly
                const inputKey = selectedWorkflow!.value === 'health-check' ? 'path' : 'target';
                const args = ['workflow', 'run', selectedWorkflow!.value, '--input', JSON.stringify({ [inputKey]: targetPath })];

                cp.execFile('empathy', args, { cwd: workspaceFolder, maxBuffer: 1024 * 1024 * 5 }, (error, stdout, stderr) => {
                    const output = stdout || stderr || (error ? error.message : 'No output');
                    lastOutput = output;
                    const timestamp = new Date().toLocaleString();
                    panel.webview.html = getReportHtml(selectedWorkflow!.label, targetPath, timestamp, output, error?.message || null, selectedWorkflow!.value);
                });
            };

            // Run workflow initially
            runWorkflow();
        })
    );

    // Register URI handler for "Run in Empathy" buttons from documentation
    // Example URI: vscode://Smart-AI-Memory.empathy-framework/runCommand?command=empathy%20init
    context.subscriptions.push(
        vscode.window.registerUriHandler({
            handleUri(uri: vscode.Uri) {
                console.log('Empathy URI Handler received:', uri.toString());

                if (uri.path === '/runCommand') {
                    const params = new URLSearchParams(uri.query);
                    const commandToRun = params.get('command');

                    if (commandToRun) {
                        // Security: Only allow empathy commands
                        if (!commandToRun.startsWith('empathy')) {
                            vscode.window.showErrorMessage(
                                'Only Empathy Framework commands are allowed via URI handler.'
                            );
                            return;
                        }

                        // Find or create a terminal and run the command
                        let terminal = vscode.window.terminals.find(t => t.name === 'Empathy Docs');
                        if (!terminal) {
                            terminal = vscode.window.createTerminal('Empathy Docs');
                        }
                        terminal.show();
                        terminal.sendText(commandToRun);

                        vscode.window.showInformationMessage(
                            `Running: ${commandToRun}`
                        );
                    } else {
                        vscode.window.showWarningMessage(
                            'No command specified in URI. Use ?command=empathy%20...'
                        );
                    }
                } else if (uri.path === '/openWorkflow') {
                    // Alternative: Open a specific workflow in the dashboard
                    const params = new URLSearchParams(uri.query);
                    const workflow = params.get('workflow');

                    if (workflow) {
                        // Focus the dashboard and trigger the workflow
                        vscode.commands.executeCommand('empathy-dashboard.focus');
                        vscode.window.showInformationMessage(
                            `Opening workflow: ${workflow}`
                        );
                    }
                } else {
                    vscode.window.showWarningMessage(
                        `Unknown Empathy URI path: ${uri.path}. Use /runCommand or /openWorkflow.`
                    );
                }
            }
        })
    );

    // Initialize
    updateStatusBar();
    startAutoRefresh(context);
    setupAutoScanOnSave(context); // Feature E
    setupSecurityFindingsWatcher(context); // Security diagnostics
    setupPeriodicHealthScan(context); // Auto-regenerate health.json

    // Show welcome message on first activation
    showWelcomeIfNeeded(context);

    // Load initial diagnostics (Feature F)
    healthProvider.updateDiagnostics();
    healthProvider.updateSecurityDiagnostics(); // Load persisted security findings
}

/**
 * Extension deactivation
 */
export function deactivate() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
    if (healthScanTimer) {
        clearInterval(healthScanTimer);
    }
    if (fileWatcher) {
        fileWatcher.dispose();
    }
    if (securityFindingsWatcher) {
        securityFindingsWatcher.dispose();
    }
    if (diagnosticCollection) {
        diagnosticCollection.dispose();
    }
    if (securityDiagnosticCollection) {
        securityDiagnosticCollection.dispose();
    }
}

// ============================================================================
// Command Handlers
// ============================================================================

async function cmdMorning() {
    // Run morning briefing and open in styled webview panel
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    const config = vscode.workspace.getConfiguration('empathy');
    const pythonPath = config.get<string>('pythonPath', 'python');
    const args = ['-m', 'empathy_os.cli', 'morning'];

    // Show progress notification
    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'Empathy: Generating morning briefing...',
            cancellable: false,
        },
        async () => {
            return new Promise<void>((resolve, reject) => {
                cp.execFile(pythonPath, args, { cwd: workspaceFolder, maxBuffer: 1024 * 1024 * 5 }, async (error, stdout, stderr) => {
                    const output = stdout || stderr || (error ? error.message : 'No output');

                    if (error && !stdout) {
                        vscode.window.showErrorMessage(`Morning briefing failed: ${error.message}`);
                        reject(error);
                        return;
                    }

                    // Open in styled webview panel
                    try {
                        const extensionUri = vscode.extensions.getExtension('smart-ai-memory.empathy-framework')?.extensionUri;
                        if (extensionUri) {
                            MorningBriefingPanel.createOrShow(extensionUri, output);
                        }
                        resolve();
                    } catch (openErr) {
                        vscode.window.showErrorMessage(`Failed to open briefing panel: ${openErr}`);
                        reject(openErr);
                    }
                });
            });
        }
    );
}

async function cmdShip() {
    runEmpathyCommand('ship', 'Pre-Ship Check');
}

async function cmdFixAll() {
    await runEmpathyCommandWithProgress('fix-all', 'Fixing all issues...');
    healthProvider.refresh();
}

async function cmdLearn() {
    runEmpathyCommand('learn --analyze 20', 'Learning Patterns');
}

async function cmdCosts() {
    runEmpathyCommand('costs', 'API Costs');
}

async function cmdDashboard() {
    runEmpathyCommand('dashboard', 'Dashboard', { background: true });
    vscode.window.showInformationMessage(
        'Empathy Dashboard started. Check your browser.'
    );
}

async function cmdSyncClaude() {
    runEmpathyCommand('sync-claude', 'Sync to Claude Code');
}

async function cmdStatus() {
    const data = await getStatusData();
    if (data) {
        const message = [
            `Patterns: ${data.patterns} learned`,
            `Health: ${data.health}`,
            `Costs: $${data.savings.toFixed(2)} saved`,
        ].join(' | ');
        vscode.window.showInformationMessage(`Empathy Status: ${message}`);
    }
}

// Feature A: Quick Fix for Lint
async function cmdFixLint() {
    vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'Empathy: Fixing lint issues...',
            cancellable: false,
        },
        async () => {
            await runEmpathyCommandSilent('fix-all --lint-only');
            healthProvider.refresh();
            vscode.window.showInformationMessage('Lint issues fixed!');
        }
    );
}

// Feature A: Quick Fix for Format
async function cmdFixFormat() {
    vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'Empathy: Formatting code...',
            cancellable: false,
        },
        async () => {
            await runEmpathyCommandSilent('fix-all --format-only');
            healthProvider.refresh();
            vscode.window.showInformationMessage('Code formatted!');
        }
    );
}

// Feature B: Refresh Health / Run Scan
async function cmdRefreshHealth() {
    healthProvider.refresh();
    healthProvider.updateDiagnostics();
    vscode.window.showInformationMessage('Health data refreshed');
}

async function cmdRunScan() {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'Empathy: Running health scan...',
            cancellable: false,
        },
        async () => {
            // Run actual health checks via bundled Python script
            const config = vscode.workspace.getConfiguration('empathy');
            const pythonPath = config.get<string>('pythonPath', 'python');
            const empathyDir = path.join(workspaceFolder, config.get<string>('empathyDir', '.empathy'));

            // Ensure .empathy directory exists
            if (!fs.existsSync(empathyDir)) {
                fs.mkdirSync(empathyDir, { recursive: true });
            }

            // Path to bundled health scan script (safe - no shell interpolation)
            const healthScriptPath = path.join(extensionPath, 'scripts', 'health_scan.py');

            return new Promise<void>((resolve) => {
                // Use execFile with array arguments to prevent command injection
                cp.execFile(pythonPath, [healthScriptPath, workspaceFolder, empathyDir],
                    { cwd: workspaceFolder, timeout: 60000 },
                    (error) => {
                        healthProvider.refresh();
                        healthProvider.updateDiagnostics();
                        updateStatusBar();
                        if (error) {
                            vscode.window.showWarningMessage('Health scan completed with warnings');
                        } else {
                            vscode.window.showInformationMessage('Health scan complete!');
                        }
                        resolve();
                    }
                );
            });
        }
    );
}

// Security Scan with diagnostics integration
async function cmdRunSecurityScan() {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'Empathy: Running security scan...',
            cancellable: false,
        },
        async () => {
            const config = vscode.workspace.getConfiguration('empathy');
            const pythonPath = config.get<string>('pythonPath', 'python');
            const empathyDir = path.join(workspaceFolder, config.get<string>('empathyDir', '.empathy'));

            // Ensure .empathy directory exists
            if (!fs.existsSync(empathyDir)) {
                fs.mkdirSync(empathyDir, { recursive: true });
            }

            return new Promise<void>((resolve) => {
                // v4.6.3: Run security-audit workflow with JSON output
                const args = [
                    'workflow', 'run', 'security-audit',
                    '--input', JSON.stringify({ target: workspaceFolder }),
                    '--json'
                ];

                cp.execFile('empathy', args, {
                    cwd: workspaceFolder,
                    maxBuffer: 1024 * 1024 * 5, // 5MB buffer for large outputs
                    timeout: 120000 // 2 minute timeout
                }, (error, stdout, stderr) => {
                    try {
                        // Try to parse JSON output
                        const output = stdout || stderr || '';
                        const result = JSON.parse(output);

                        // Save findings to file
                        const findingsPath = path.join(empathyDir, 'security_findings.json');
                        fs.writeFileSync(findingsPath, JSON.stringify(result, null, 2));

                        // Update diagnostics
                        healthProvider.updateSecurityDiagnostics();

                        // Show summary notification
                        const assessment = result.assessment || {};
                        const breakdown = assessment.severity_breakdown || {};
                        const critical = breakdown.critical || 0;
                        const high = breakdown.high || 0;
                        const medium = breakdown.medium || 0;
                        const low = breakdown.low || 0;
                        const total = critical + high + medium + low;

                        if (critical > 0 || high > 0) {
                            vscode.window.showWarningMessage(
                                `Security scan: ${critical} critical, ${high} high, ${medium} medium, ${low} low findings. Check Problems panel.`
                            );
                        } else if (total > 0) {
                            vscode.window.showInformationMessage(
                                `Security scan complete: ${medium} medium, ${low} low findings`
                            );
                        } else {
                            vscode.window.showInformationMessage('Security scan complete - no issues found!');
                        }
                    } catch (parseErr) {
                        // JSON parse failed - maybe text output or error
                        if (error) {
                            vscode.window.showWarningMessage(`Security scan completed with errors: ${error.message}`);
                        } else {
                            vscode.window.showInformationMessage('Security scan complete');
                        }
                        console.error('Failed to parse security scan output:', parseErr);
                    }
                    resolve();
                });
            });
        }
    );
}

// Feature C: Run Tests
async function cmdRunTests() {
    runEmpathyCommand('ship --tests-only', 'Running Tests');
}

// Feature C: Open file at location
async function cmdOpenFile(filePath?: string, line?: number) {
    if (!filePath) {
        return;
    }
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        return;
    }

    const fullPath = path.isAbsolute(filePath)
        ? filePath
        : path.join(workspaceFolder, filePath);

    try {
        const doc = await vscode.workspace.openTextDocument(fullPath);
        const editor = await vscode.window.showTextDocument(doc);
        if (line && line > 0) {
            const position = new vscode.Position(line - 1, 0);
            editor.selection = new vscode.Selection(position, position);
            editor.revealRange(new vscode.Range(position, position));
        }
    } catch (err) {
        vscode.window.showErrorMessage(`Could not open file: ${filePath}`);
    }
}

// Feature D: View Details
async function cmdViewDetails(item?: HealthItem) {
    if (!item) {
        return;
    }

    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        return;
    }

    // Show quick pick with options based on item type
    const options: string[] = [];
    if (item.label === 'Lint' || item.label === 'Types') {
        options.push('Fix Issues', 'Show in Terminal', 'View Report');
    } else if (item.label === 'Security') {
        options.push('View Report', 'Run Security Scan');
    } else if (item.label === 'Tests') {
        options.push('Run Tests', 'View Coverage Report');
    } else if (item.label === 'Tech Debt') {
        options.push('View Hotspots', 'Search TODOs');
    } else {
        options.push('Refresh', 'Open Dashboard');
    }

    const selected = await vscode.window.showQuickPick(options, {
        placeHolder: `Actions for ${item.label}`,
    });

    if (!selected) {
        return;
    }

    switch (selected) {
        case 'Fix Issues':
            cmdFixAll();
            break;
        case 'Show in Terminal':
            runEmpathyCommand('ship --verbose', 'Health Check');
            break;
        case 'View Report':
            runEmpathyCommand('dashboard', 'Dashboard', { background: true });
            break;
        case 'Run Security Scan':
            runEmpathyCommand('ship --security-only', 'Security Scan');
            break;
        case 'Run Tests':
            cmdRunTests();
            break;
        case 'View Coverage Report':
            const coverageFile = path.join(workspaceFolder, 'htmlcov', 'index.html');
            if (fs.existsSync(coverageFile)) {
                vscode.env.openExternal(vscode.Uri.file(coverageFile));
            } else {
                vscode.window.showWarningMessage('No coverage report found. Run tests first.');
            }
            break;
        case 'View Hotspots':
            runEmpathyCommand('patterns hotspots', 'Tech Debt Hotspots');
            break;
        case 'Search TODOs':
            vscode.commands.executeCommand('workbench.action.findInFiles', {
                query: 'TODO|FIXME|HACK',
                isRegex: true,
            });
            break;
        case 'Refresh':
            cmdRefreshHealth();
            break;
        case 'Open Dashboard':
            cmdDashboard();
            break;
    }
}

// Feature D: Ignore Issue (add to baseline)
async function cmdIgnoreIssue(item?: HealthItem) {
    if (!item) {
        return;
    }

    const reason = await vscode.window.showInputBox({
        prompt: 'Reason for ignoring this issue (optional)',
        placeHolder: 'e.g., False positive, Will fix in Q2',
    });

    if (reason === undefined) {
        return; // Cancelled
    }

    vscode.window.showInformationMessage(
        `Issue "${item.label}" would be added to baseline. (Feature coming soon)`
    );
}

// Open Full Web Dashboard
async function cmdOpenWebDashboard() {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    const config = vscode.workspace.getConfiguration('empathy');
    const pythonPath = config.get<string>('pythonPath', 'python');

    // Check if dashboard server is already running
    try {
        const http = await import('http');
        const isRunning = await new Promise<boolean>((resolve) => {
            const req = http.request(
                { host: 'localhost', port: 8765, path: '/api/health', timeout: 1000 },
                (res) => resolve(res.statusCode === 200)
            );
            req.on('error', () => resolve(false));
            req.on('timeout', () => { req.destroy(); resolve(false); });
            req.end();
        });

        if (isRunning) {
            vscode.env.openExternal(vscode.Uri.parse('http://localhost:8765'));
            return;
        }
    } catch {
        // Server not running, continue to start it
    }

    // Start the dashboard server
    vscode.window.showInformationMessage('Starting Empathy Web Dashboard...');

    const proc = cp.spawn(pythonPath, ['-m', 'empathy_os.cli', 'dashboard', '--no-browser'], {
        cwd: workspaceFolder.uri.fsPath,
        detached: true,
        stdio: 'ignore'
    });
    proc.unref();

    // Wait for server to start, then open browser
    setTimeout(() => {
        vscode.env.openExternal(vscode.Uri.parse('http://localhost:8765'));
    }, 2500);
}

// ============================================================================
// Empathy Command Runner
// ============================================================================

interface RunOptions {
    background?: boolean;
}

async function runEmpathyCommand(
    command: string,
    title: string,
    options: RunOptions = {}
): Promise<void> {
    const config = vscode.workspace.getConfiguration('empathy');
    const pythonPath = config.get<string>('pythonPath', 'python');
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

    if (!workspaceFolder) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    // Build arguments as array for safe execution (no shell interpolation)
    const args = ['-m', 'empathy_os.cli', ...command.split(/\s+/)];

    if (options.background) {
        // Use execFile with array arguments to prevent command injection
        cp.execFile(pythonPath, args, { cwd: workspaceFolder });
        return;
    }

    // Show in terminal (terminal.sendText is safe - no shell injection risk)
    const terminal = vscode.window.createTerminal({
        name: `Empathy: ${title}`,
        cwd: workspaceFolder,
    });
    terminal.show();
    terminal.sendText(`${pythonPath} -m empathy_os.cli ${command}`);
}

async function runEmpathyCommandSilent(command: string): Promise<string> {
    return new Promise((resolve, reject) => {
        const config = vscode.workspace.getConfiguration('empathy');
        const pythonPath = config.get<string>('pythonPath', 'python');
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

        if (!workspaceFolder) {
            reject(new Error('No workspace folder open'));
            return;
        }

        // Build arguments as array for safe execution (no shell interpolation)
        const args = ['-m', 'empathy_os.cli', ...command.split(/\s+/)];

        // Use execFile with array arguments to prevent command injection
        cp.execFile(pythonPath, args, { cwd: workspaceFolder }, (error, stdout, stderr) => {
            if (error) {
                reject(error);
            } else {
                resolve(stdout);
            }
        });
    });
}

async function runEmpathyCommandWithProgress(command: string, message: string): Promise<void> {
    return vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: `Empathy: ${message}`,
            cancellable: false,
        },
        async () => {
            await runEmpathyCommandSilent(command);
        }
    );
}

// ============================================================================
// Feature E: Auto-Scan on Save
// ============================================================================

/**
 * Set up periodic health scan to regenerate health.json automatically
 * This ensures the dashboard always shows up-to-date health metrics
 */
function setupPeriodicHealthScan(context: vscode.ExtensionContext): void {
    const config = vscode.workspace.getConfiguration('empathy');
    const runOnStartup = config.get<boolean>('runHealthScanOnStartup', true);
    const scanIntervalMinutes = config.get<number>('healthScanInterval', 30);

    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        return;
    }

    const pythonPath = config.get<string>('pythonPath', 'python');
    const empathyDir = path.join(workspaceFolder, config.get<string>('empathyDir', '.empathy'));

    // Ensure .empathy directory exists
    if (!fs.existsSync(empathyDir)) {
        fs.mkdirSync(empathyDir, { recursive: true });
    }

    // Function to run the health scan silently
    const runHealthScanSilent = () => {
        const healthScriptPath = path.join(extensionPath, 'scripts', 'health_scan.py');

        if (!fs.existsSync(healthScriptPath)) {
            console.log('[Empathy] Health scan script not found, skipping auto-scan');
            return;
        }

        cp.execFile(pythonPath, [healthScriptPath, workspaceFolder, empathyDir],
            { cwd: workspaceFolder, timeout: 60000 },
            (error) => {
                if (error) {
                    console.log('[Empathy] Background health scan completed with warnings');
                } else {
                    console.log('[Empathy] Background health scan completed successfully');
                }
                // Refresh UI after scan
                healthProvider.refresh();
                healthProvider.updateDiagnostics();
                updateStatusBar();
            }
        );
    };

    // Run on startup if enabled
    if (runOnStartup) {
        // Delay startup scan by 5 seconds to let VS Code finish loading
        setTimeout(() => {
            console.log('[Empathy] Running health scan on startup...');
            runHealthScanSilent();
        }, 5000);
    }

    // Set up periodic scan if interval is positive
    if (scanIntervalMinutes > 0) {
        const intervalMs = scanIntervalMinutes * 60 * 1000;
        healthScanTimer = setInterval(() => {
            console.log('[Empathy] Running periodic health scan...');
            runHealthScanSilent();
        }, intervalMs);
        console.log(`[Empathy] Periodic health scan enabled: every ${scanIntervalMinutes} minutes`);
    }
}

function setupAutoScanOnSave(context: vscode.ExtensionContext): void {
    const config = vscode.workspace.getConfiguration('empathy');
    const autoScanEnabled = config.get<boolean>('autoScanOnSave', false);

    if (!autoScanEnabled) {
        return;
    }

    // Watch for Python file saves
    fileWatcher = vscode.workspace.createFileSystemWatcher('**/*.py');

    // Debounce mechanism
    let scanTimeout: NodeJS.Timeout | undefined;

    const debouncedScan = () => {
        if (scanTimeout) {
            clearTimeout(scanTimeout);
        }
        scanTimeout = setTimeout(async () => {
            try {
                await runEmpathyCommandSilent('ship --quick --silent');
                healthProvider.refresh();
                healthProvider.updateDiagnostics();
            } catch {
                // Ignore errors in background scan
            }
        }, 2000); // Wait 2 seconds after last save
    };

    fileWatcher.onDidChange(debouncedScan);
    fileWatcher.onDidCreate(debouncedScan);

    context.subscriptions.push(fileWatcher);
}

/**
 * Set up file watcher for security findings
 * Refreshes diagnostics when security_findings.json changes
 */
function setupSecurityFindingsWatcher(context: vscode.ExtensionContext): void {
    // Watch for changes to security_findings.json
    securityFindingsWatcher = vscode.workspace.createFileSystemWatcher('**/.empathy/security_findings.json');

    securityFindingsWatcher.onDidChange(() => {
        healthProvider.updateSecurityDiagnostics();
    });

    securityFindingsWatcher.onDidCreate(() => {
        healthProvider.updateSecurityDiagnostics();
    });

    securityFindingsWatcher.onDidDelete(() => {
        // Clear security diagnostics when file is deleted
        securityDiagnosticCollection.clear();
    });

    context.subscriptions.push(securityFindingsWatcher);

    // Register meta-workflow commands
    try {
        console.log('[Empathy] About to register meta-workflow commands...');
        registerMetaWorkflowCommands(context);
        console.log('[Empathy] Meta-workflow commands registered SUCCESS');
    } catch (error) {
        console.error('[Empathy] ERROR registering meta-workflow commands:', error);
        vscode.window.showErrorMessage(`Failed to register meta-workflow commands: ${error}`);
    }
}

// ============================================================================
// Status Bar
// ============================================================================

interface StatusData {
    patterns: number;
    health: string;
    savings: number;
}

async function getStatusData(): Promise<StatusData | null> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        return null;
    }

    const config = vscode.workspace.getConfiguration('empathy');
    const patternsDir = path.join(
        workspaceFolder,
        config.get<string>('patternsDir', './patterns')
    );
    const empathyDir = path.join(
        workspaceFolder,
        config.get<string>('empathyDir', '.empathy')
    );

    let patterns = 0;
    let savings = 0;

    // Count patterns
    try {
        const debuggingFile = path.join(patternsDir, 'debugging.json');
        if (fs.existsSync(debuggingFile)) {
            const data = JSON.parse(fs.readFileSync(debuggingFile, 'utf8'));
            patterns = data.patterns?.length || 0;
        }
    } catch {
        // Ignore errors
    }

    // Get cost savings
    try {
        const costsFile = path.join(empathyDir, 'costs.json');
        if (fs.existsSync(costsFile)) {
            const data = JSON.parse(fs.readFileSync(costsFile, 'utf8'));
            // Sum up daily savings
            for (const daily of Object.values(data.daily_totals || {})) {
                savings += (daily as any).savings || 0;
            }
        }
    } catch {
        // Ignore errors
    }

    return {
        patterns,
        health: patterns > 0 ? 'OK' : 'Setup needed',
        savings,
    };
}

async function updateStatusBar(): Promise<void> {
    const config = vscode.workspace.getConfiguration('empathy');
    if (!config.get<boolean>('showStatusBar', true)) {
        statusBarItem.hide();
        return;
    }

    const data = await getStatusData();
    if (!data) {
        statusBarItem.text = '$(pulse) Empathy';
        statusBarItem.tooltip = 'No workspace open';
    } else if (data.patterns === 0) {
        statusBarItem.text = '$(pulse) Empathy: Setup';
        statusBarItem.tooltip = 'Run "empathy learn" to get started';
    } else {
        statusBarItem.text = `$(pulse) ${data.patterns} patterns | $${data.savings.toFixed(2)} saved`;
        statusBarItem.tooltip = `Empathy Framework\nPatterns: ${data.patterns}\nSavings: $${data.savings.toFixed(2)}`;
    }
    statusBarItem.show();
}

function startAutoRefresh(context: vscode.ExtensionContext): void {
    const config = vscode.workspace.getConfiguration('empathy');
    const autoRefresh = config.get<boolean>('autoRefresh', true);
    const interval = config.get<number>('refreshInterval', 300) * 1000;

    if (autoRefresh && interval > 0) {
        refreshTimer = setInterval(() => {
            updateStatusBar();
            healthProvider.refresh();
        }, interval);
    }
}

// ============================================================================
// Health Provider (for diagnostics)
// ============================================================================

class HealthTreeProvider implements vscode.TreeDataProvider<HealthItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<HealthItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    private cachedHealth: HealthData | null = null;
    private diagnosticCollection: vscode.DiagnosticCollection;
    private securityDiagnosticCollection: vscode.DiagnosticCollection;

    constructor(diagnosticCollection: vscode.DiagnosticCollection, securityDiagnosticCollection: vscode.DiagnosticCollection) {
        this.diagnosticCollection = diagnosticCollection;
        this.securityDiagnosticCollection = securityDiagnosticCollection;
    }

    refresh(): void {
        this.cachedHealth = null;
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: HealthItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: HealthItem): Promise<HealthItem[]> {
        // If this is a child element, return its details
        if (element && element.children) {
            return element.children;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            return [new HealthItem('No workspace', 'Open a folder to inspect', 'unknown')];
        }

        // Get health data from files or cache
        const health = await this.getHealthData(workspaceFolder);

        const items: HealthItem[] = [];

        // Overall Health Score - clickable to run scan
        const scoreIcon = health.score >= 80 ? 'ok' : health.score >= 50 ? 'warning' : 'error';
        const scoreItem = new HealthItem(
            'Health Score',
            `${health.score}%`,
            scoreIcon,
            undefined,
            'Overall code health score - click to scan'
        );
        scoreItem.command = { command: 'empathy.runScan', title: 'Run Scan' };
        scoreItem.contextValue = 'healthScore';
        items.push(scoreItem);

        // Patterns Learned
        const patternsItem = new HealthItem(
            'Patterns Learned',
            `${health.patterns} bugs tracked`,
            health.patterns > 0 ? 'ok' : 'unknown',
            undefined,
            'Bug patterns learned from git history'
        );
        patternsItem.command = { command: 'empathy.learn', title: 'Learn Patterns' };
        patternsItem.contextValue = 'patterns';
        items.push(patternsItem);

        // Lint Issues - with fix action
        const lintStatus = health.lint.errors === 0 ? 'ok' : health.lint.errors > 10 ? 'error' : 'warning';
        const lintItem = new HealthItem(
            'Lint',
            `${health.lint.errors} errors, ${health.lint.warnings} warnings`,
            lintStatus,
            [
                new HealthItem('Errors', health.lint.errors.toString(), health.lint.errors === 0 ? 'ok' : 'error'),
                new HealthItem('Warnings', health.lint.warnings.toString(), health.lint.warnings === 0 ? 'ok' : 'warning'),
            ],
            'Linting issues from ruff/pylint - click to fix'
        );
        lintItem.command = { command: 'empathy.fixLint', title: 'Fix Lint' };
        lintItem.contextValue = 'lint';
        items.push(lintItem);

        // Type Checking
        const typeStatus = health.types.errors === 0 ? 'ok' : 'error';
        const typesItem = new HealthItem(
            'Types',
            health.types.errors === 0 ? 'All types valid' : `${health.types.errors} type errors`,
            typeStatus,
            undefined,
            'MyPy type checking results'
        );
        typesItem.contextValue = 'types';
        items.push(typesItem);

        // Security
        const secStatus = health.security.high === 0 && health.security.medium === 0 ? 'ok' :
                         health.security.high > 0 ? 'error' : 'warning';
        const secItem = new HealthItem(
            'Security',
            `${health.security.high} high, ${health.security.medium} medium`,
            secStatus,
            [
                new HealthItem('High Severity', health.security.high.toString(), health.security.high === 0 ? 'ok' : 'error'),
                new HealthItem('Medium Severity', health.security.medium.toString(), health.security.medium === 0 ? 'ok' : 'warning'),
                new HealthItem('Low Severity', health.security.low.toString(), 'ok'),
            ],
            'Security vulnerabilities from bandit'
        );
        secItem.contextValue = 'security';
        items.push(secItem);

        // Tests - with run action
        const testStatus = health.tests.failed === 0 ? 'ok' : 'error';
        const testItem = new HealthItem(
            'Tests',
            `${health.tests.passed}/${health.tests.total} passing`,
            testStatus,
            [
                new HealthItem('Passed', health.tests.passed.toString(), 'ok'),
                new HealthItem('Failed', health.tests.failed.toString(), health.tests.failed === 0 ? 'ok' : 'error'),
                new HealthItem('Coverage', `${health.tests.coverage}%`, health.tests.coverage >= 70 ? 'ok' : 'warning'),
            ],
            'Test suite status and coverage - click to run'
        );
        testItem.command = { command: 'empathy.runTests', title: 'Run Tests' };
        testItem.contextValue = 'tests';
        items.push(testItem);

        // Tech Debt
        const debtStatus = health.techDebt.total < 50 ? 'ok' : health.techDebt.total < 200 ? 'warning' : 'error';
        const debtItem = new HealthItem(
            'Tech Debt',
            `${health.techDebt.total} items`,
            debtStatus,
            [
                new HealthItem('TODOs', health.techDebt.todos.toString(), 'info'),
                new HealthItem('FIXMEs', health.techDebt.fixmes.toString(), health.techDebt.fixmes === 0 ? 'ok' : 'warning'),
                new HealthItem('HACKs', health.techDebt.hacks.toString(), health.techDebt.hacks === 0 ? 'ok' : 'error'),
            ],
            'Technical debt from code annotations'
        );
        debtItem.contextValue = 'techDebt';
        items.push(debtItem);

        // Last Updated - with refresh action
        const lastScanItem = new HealthItem(
            'Last Scan',
            health.lastUpdated || 'Never',
            'info',
            undefined,
            'Click to refresh'
        );
        lastScanItem.command = { command: 'empathy.refreshHealth', title: 'Refresh' };
        lastScanItem.contextValue = 'lastScan';
        items.push(lastScanItem);

        return items;
    }

    // Feature F: Update Problem Panel diagnostics
    async updateDiagnostics(): Promise<void> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            return;
        }

        this.diagnosticCollection.clear();

        const config = vscode.workspace.getConfiguration('empathy');
        const empathyDir = path.join(
            workspaceFolder,
            config.get<string>('empathyDir', '.empathy')
        );

        // Read issues from inspection results
        try {
            const issuesFile = path.join(empathyDir, 'issues.json');
            if (!fs.existsSync(issuesFile)) {
                return;
            }

            const data = JSON.parse(fs.readFileSync(issuesFile, 'utf8'));
            const diagnosticsMap = new Map<string, vscode.Diagnostic[]>();

            for (const issue of data.issues || []) {
                const filePath = issue.file || '';
                const line = (issue.line || 1) - 1;
                const message = issue.message || 'Unknown issue';
                const severity = this.getSeverity(issue.severity || 'warning');

                const range = new vscode.Range(line, 0, line, 1000);
                const diagnostic = new vscode.Diagnostic(range, message, severity);
                diagnostic.source = 'Empathy';
                diagnostic.code = issue.rule || issue.type || 'empathy';

                const fullPath = path.isAbsolute(filePath)
                    ? filePath
                    : path.join(workspaceFolder, filePath);

                if (!diagnosticsMap.has(fullPath)) {
                    diagnosticsMap.set(fullPath, []);
                }
                diagnosticsMap.get(fullPath)!.push(diagnostic);
            }

            // Apply diagnostics
            for (const [file, diagnostics] of diagnosticsMap) {
                const uri = vscode.Uri.file(file);
                this.diagnosticCollection.set(uri, diagnostics);
            }
        } catch {
            // Ignore errors reading issues file
        }
    }

    private getSeverity(level: string): vscode.DiagnosticSeverity {
        switch (level.toLowerCase()) {
            case 'error':
            case 'high':
            case 'critical':
                return vscode.DiagnosticSeverity.Error;
            case 'warning':
            case 'medium':
                return vscode.DiagnosticSeverity.Warning;
            case 'info':
            case 'low':
                return vscode.DiagnosticSeverity.Information;
            default:
                return vscode.DiagnosticSeverity.Hint;
        }
    }

    /**
     * Update security diagnostics from security_findings.json
     * Shows security scan findings as squiggles in the editor
     */
    async updateSecurityDiagnostics(): Promise<void> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            return;
        }

        this.securityDiagnosticCollection.clear();

        const config = vscode.workspace.getConfiguration('empathy');
        const empathyDir = path.join(
            workspaceFolder,
            config.get<string>('empathyDir', '.empathy')
        );

        try {
            const findingsFile = path.join(empathyDir, 'security_findings.json');
            if (!fs.existsSync(findingsFile)) {
                return;
            }

            const data = JSON.parse(fs.readFileSync(findingsFile, 'utf8'));
            const diagnosticsMap = new Map<string, vscode.Diagnostic[]>();

            // Only process needs_review findings (excludes false positives and accepted risks)
            const findings = data.needs_review || [];

            for (const finding of findings) {
                const filePath = finding.file || '';
                const line = (finding.line || 1) - 1;
                const severity = this.getSeverity(finding.severity || 'warning');

                // Rich message with OWASP category and analysis
                const owasp = finding.owasp || 'Security Issue';
                const findingType = finding.type || 'unknown';
                const analysis = finding.analysis || `Potential ${findingType} vulnerability`;
                const message = `[${owasp}] ${findingType}: ${analysis}`;

                const range = new vscode.Range(line, 0, line, 1000);
                const diagnostic = new vscode.Diagnostic(range, message, severity);
                diagnostic.source = 'Empathy Security';
                diagnostic.code = findingType;

                // Add code snippet as related information if available
                if (finding.match) {
                    diagnostic.relatedInformation = [
                        new vscode.DiagnosticRelatedInformation(
                            new vscode.Location(
                                vscode.Uri.file(filePath),
                                range
                            ),
                            `Match: ${finding.match.substring(0, 80)}${finding.match.length > 80 ? '...' : ''}`
                        )
                    ];
                }

                const fullPath = path.isAbsolute(filePath)
                    ? filePath
                    : path.join(workspaceFolder, filePath);

                if (!diagnosticsMap.has(fullPath)) {
                    diagnosticsMap.set(fullPath, []);
                }
                diagnosticsMap.get(fullPath)!.push(diagnostic);
            }

            // Apply diagnostics
            for (const [file, diagnostics] of diagnosticsMap) {
                const uri = vscode.Uri.file(file);
                this.securityDiagnosticCollection.set(uri, diagnostics);
            }
        } catch (err) {
            console.error('Failed to load security findings:', err);
        }
    }

    private async getHealthData(workspaceFolder: string): Promise<HealthData> {
        if (this.cachedHealth) {
            return this.cachedHealth;
        }

        const config = vscode.workspace.getConfiguration('empathy');
        const empathyDir = path.join(
            workspaceFolder,
            config.get<string>('empathyDir', '.empathy')
        );
        const patternsDir = path.join(
            workspaceFolder,
            config.get<string>('patternsDir', './patterns')
        );

        // Default health data
        const health: HealthData = {
            score: 0,
            patterns: 0,
            lint: { errors: 0, warnings: 0 },
            types: { errors: 0 },
            security: { high: 0, medium: 0, low: 0 },
            tests: { passed: 0, failed: 0, total: 0, coverage: 0 },
            techDebt: { total: 0, todos: 0, fixmes: 0, hacks: 0 },
            lastUpdated: null,
        };

        // Read patterns count
        try {
            const debuggingFile = path.join(patternsDir, 'debugging.json');
            if (fs.existsSync(debuggingFile)) {
                const data = JSON.parse(fs.readFileSync(debuggingFile, 'utf8'));
                health.patterns = data.patterns?.length || 0;
            }
        } catch { /* ignore */ }

        // Read health.json if exists (from empathy-inspect or ship)
        try {
            const healthFile = path.join(empathyDir, 'health.json');
            if (fs.existsSync(healthFile)) {
                const data = JSON.parse(fs.readFileSync(healthFile, 'utf8'));
                health.score = data.score || 0;
                health.lint = data.lint || health.lint;
                health.types = data.types || health.types;
                health.security = data.security || health.security;
                health.tests = data.tests || health.tests;
                health.techDebt = data.tech_debt || health.techDebt;
                health.lastUpdated = data.timestamp ? new Date(data.timestamp).toLocaleString() : null;
            }
        } catch { /* ignore */ }

        // Read tech debt from patterns if available
        try {
            const debtFile = path.join(patternsDir, 'tech_debt.json');
            if (fs.existsSync(debtFile)) {
                const data = JSON.parse(fs.readFileSync(debtFile, 'utf8'));
                if (data.snapshots && data.snapshots.length > 0) {
                    const latest = data.snapshots[data.snapshots.length - 1];
                    health.techDebt.total = latest.total_items || 0;
                    if (latest.by_type) {
                        health.techDebt.todos = latest.by_type.todo || 0;
                        health.techDebt.fixmes = latest.by_type.fixme || 0;
                        health.techDebt.hacks = latest.by_type.hack || 0;
                    }
                }
            }
        } catch { /* ignore */ }

        // Calculate score if not set
        if (health.score === 0) {
            let score = 100;
            score -= health.lint.errors * 2;
            score -= health.lint.warnings * 0.5;
            score -= health.types.errors * 3;
            score -= health.security.high * 10;
            score -= health.security.medium * 5;
            score -= health.tests.failed * 5;
            score -= Math.max(0, 70 - health.tests.coverage);
            health.score = Math.max(0, Math.min(100, Math.round(score)));
        }

        this.cachedHealth = health;
        return health;
    }
}

interface HealthData {
    score: number;
    patterns: number;
    lint: { errors: number; warnings: number };
    types: { errors: number };
    security: { high: number; medium: number; low: number };
    tests: { passed: number; failed: number; total: number; coverage: number };
    techDebt: { total: number; todos: number; fixmes: number; hacks: number };
    lastUpdated: string | null;
}

class HealthItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly value: string,
        public readonly status: string,
        public readonly children?: HealthItem[],
        public readonly fullTooltip?: string
    ) {
        super(
            label,
            children ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None
        );
        this.description = value;
        this.tooltip = fullTooltip || `${label}: ${value}`;

        // Set icon based on status
        switch (status) {
            case 'ok':
                this.iconPath = new vscode.ThemeIcon('check', new vscode.ThemeColor('testing.iconPassed'));
                break;
            case 'warning':
                this.iconPath = new vscode.ThemeIcon('warning', new vscode.ThemeColor('editorWarning.foreground'));
                break;
            case 'error':
                this.iconPath = new vscode.ThemeIcon('error', new vscode.ThemeColor('testing.iconFailed'));
                break;
            case 'info':
                this.iconPath = new vscode.ThemeIcon('info');
                break;
            default:
                this.iconPath = new vscode.ThemeIcon('question');
        }
    }
}

// ============================================================================
// Welcome Message
// ============================================================================

function showWelcomeIfNeeded(context: vscode.ExtensionContext): void {
    const hasShownWelcome = context.globalState.get<boolean>('hasShownWelcome');
    const isInitialized = context.globalState.get<boolean>('empathy.initialized');

    if (!hasShownWelcome) {
        // First-time users get the initialize option prominently
        if (!isInitialized) {
            vscode.window
                .showInformationMessage(
                    'Welcome to Empathy Framework! Set up your project to get started.',
                    'Initialize Project',
                    'Later'
                )
                .then((selection) => {
                    if (selection === 'Initialize Project') {
                        initializeProject(context);
                    }
                });
        } else {
            vscode.window
                .showInformationMessage(
                    'Empathy Framework extension activated! Run "empathy morning" to get started.',
                    'Open Command Palette',
                    'Dismiss'
                )
                .then((selection) => {
                    if (selection === 'Open Command Palette') {
                        vscode.commands.executeCommand(
                            'workbench.action.showCommands',
                            'Empathy'
                        );
                    }
                });
        }
        context.globalState.update('hasShownWelcome', true);
    }
}

// ============================================================================
// WebView HTML Helpers for Quick Workflow Command
// ============================================================================

function escapeHtml(text: string): string {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function getLoadingHtml(displayName: string, targetPath: string): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${displayName} Report</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            margin: 0;
            padding: 40px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 80vh;
        }
        .container { text-align: center; max-width: 500px; }
        h1 { color: var(--vscode-foreground); margin-bottom: 8px; font-size: 24px; }
        .target { color: var(--vscode-descriptionForeground); font-size: 14px; margin-bottom: 40px; }
        .spinner {
            width: 60px; height: 60px;
            border: 4px solid var(--vscode-input-border);
            border-top-color: var(--vscode-button-background);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 40px auto;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .status { margin-top: 24px; font-size: 16px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>${displayName} Report</h1>
        <div class="target">Target: ${escapeHtml(targetPath)}</div>
        <div class="spinner"></div>
        <div class="status">Generating report...</div>
    </div>
</body>
</html>`;
}

function getReportHtml(displayName: string, targetPath: string, timestamp: string, output: string, errorMessage: string | null, _workflowName?: string): string {
    const isError = errorMessage !== null;
    const statusColor = isError ? 'var(--vscode-errorForeground)' : 'var(--vscode-testing-iconPassed)';
    const statusText = isError ? 'Error' : 'Complete';
    const statusIcon = isError ? '✗' : '✓';
    const statusBg = isError ? 'rgba(241, 76, 76, 0.15)' : 'rgba(115, 201, 145, 0.15)';

    // Simple markdown-like rendering for headers and code blocks
    const formattedOutput = formatMarkdown(output);

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${displayName} Report</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            margin: 0;
            padding: 24px;
            line-height: 1.6;
        }
        .header {
            border-bottom: 1px solid var(--vscode-input-border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        .header-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }
        h1 {
            color: var(--vscode-foreground);
            margin: 0;
            font-size: 24px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .actions {
            display: flex;
            gap: 8px;
        }
        .action-btn {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .action-btn:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }
        .action-btn.primary {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        .action-btn.primary:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            background: ${statusBg};
            color: ${statusColor};
        }
        .meta {
            display: flex;
            gap: 24px;
            font-size: 13px;
            color: var(--vscode-descriptionForeground);
        }
        .content {
            font-family: var(--vscode-editor-font-family);
            font-size: 13px;
        }
        .content h2 {
            color: var(--vscode-foreground);
            border-bottom: 1px solid var(--vscode-input-border);
            padding-bottom: 8px;
            margin-top: 24px;
        }
        .content h3 {
            color: var(--vscode-foreground);
            margin-top: 20px;
        }
        .content pre {
            background: var(--vscode-textCodeBlock-background);
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
            white-space: pre-wrap;
        }
        .content code {
            background: var(--vscode-textCodeBlock-background);
            padding: 2px 6px;
            border-radius: 3px;
            font-family: var(--vscode-editor-font-family);
        }
        .content ul, .content ol {
            padding-left: 24px;
        }
        .content li {
            margin: 4px 0;
        }
        .error-box {
            background: rgba(241, 76, 76, 0.1);
            border: 1px solid var(--vscode-errorForeground);
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .error-title {
            color: var(--vscode-errorForeground);
            font-weight: 600;
            margin-bottom: 8px;
        }
        .footer {
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid var(--vscode-input-border);
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-top">
            <h1>
                ${displayName} Report
                <span class="status-badge">${statusIcon} ${statusText}</span>
            </h1>
            <div class="actions">
                <button class="action-btn" onclick="copyReport()">📋 Copy</button>
                <button class="action-btn primary" onclick="runAgain()">🔄 Run Again</button>
            </div>
        </div>
        <div class="meta">
            <span>Target: ${escapeHtml(targetPath)}</span>
            <span>Generated: ${timestamp}</span>
        </div>
    </div>
    ${isError ? `
    <div class="error-box">
        <div class="error-title">Error Details</div>
        <div>${escapeHtml(errorMessage)}</div>
    </div>
    ` : ''}
    <div class="content">${formattedOutput}</div>
    <div class="footer">Generated by Empathy Framework</div>
    <script>
        const vscode = acquireVsCodeApi();
        function copyReport() {
            vscode.postMessage({ command: 'copy' });
        }
        function runAgain() {
            vscode.postMessage({ command: 'runAgain' });
        }
    </script>
</body>
</html>`;
}

function formatMarkdown(text: string): string {
    // Escape HTML first
    let html = escapeHtml(text);

    // Code blocks (```...```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

    // Inline code (`...`)
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Bold (**...**)
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic (*...*)
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Unordered lists (- item)
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

    // Line breaks
    html = html.replace(/\n\n/g, '</p><p>');
    html = '<p>' + html + '</p>';

    // Clean up empty paragraphs
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p>(<h[123]>)/g, '$1');
    html = html.replace(/(<\/h[123]>)<\/p>/g, '$1');
    html = html.replace(/<p>(<ul>)/g, '$1');
    html = html.replace(/(<\/ul>)<\/p>/g, '$1');
    html = html.replace(/<p>(<pre>)/g, '$1');
    html = html.replace(/(<\/pre>)<\/p>/g, '$1');

    return html;
}
