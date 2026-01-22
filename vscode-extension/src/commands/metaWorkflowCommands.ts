/**
 * Meta-Workflow Commands
 *
 * Provides VS Code command palette integration for meta-workflow CLI commands.
 * Executes Empathy Framework meta-workflow system commands.
 *
 * Copyright 2026 Smart AI Memory, LLC
 * Licensed under Fair Source 0.9
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import { MetaWorkflowReportPanel } from '../panels/MetaWorkflowReportPanel';

/**
 * Execute CLI command and show output
 */
async function executeCliCommand(command: string, args: string[]): Promise<void> {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        vscode.window.showErrorMessage('Please open a workspace folder first.');
        return;
    }

    const cwd = workspaceFolders[0].uri.fsPath;

    return new Promise((resolve, reject) => {
        const fullCommand = `empathy ${command} ${args.join(' ')}`;

        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `Running: ${fullCommand}`,
            cancellable: false
        }, async () => {
            return new Promise<void>((progressResolve) => {
                cp.exec(fullCommand, { cwd }, (error, stdout, stderr) => {
                    if (error) {
                        vscode.window.showErrorMessage(`Error: ${error.message}`);
                        reject(error);
                    } else {
                        // Show output in new document
                        const output = stdout + (stderr ? `\n\nErrors:\n${stderr}` : '');
                        vscode.workspace.openTextDocument({
                            content: output,
                            language: 'markdown'
                        }).then(doc => {
                            vscode.window.showTextDocument(doc);
                            progressResolve();
                            resolve();
                        });
                    }
                });
            });
        });
    });
}

/**
 * Execute meta-workflow via execFile and return JSON result
 */
async function executeMetaWorkflowJson(
    templateId: string,
    useDefaults: boolean = true
): Promise<any> {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        throw new Error('No workspace folder open');
    }

    const config = vscode.workspace.getConfiguration('empathy');
    const pythonPath = config.get<string>('pythonPath', 'python');

    // Determine correct working directory
    let cwd = workspaceFolders[0].uri.fsPath;
    if (cwd.endsWith('vscode-extension')) {
        cwd = path.dirname(cwd);
    }

    // v4.6.3: Use 'empathy' CLI directly
    const args = [
        'meta-workflow', 'run', templateId,
        '--real', '--json'
    ];

    if (useDefaults) {
        args.push('--use-defaults');
    }

    return new Promise((resolve, reject) => {
        cp.execFile('empathy', args, {
            cwd: cwd,
            maxBuffer: 10 * 1024 * 1024, // 10MB buffer
            timeout: 600000 // 10 minute timeout for complex workflows
        }, (error, stdout, stderr) => {
            if (error) {
                // Try to parse JSON error from stderr
                try {
                    const errorResult = JSON.parse(stderr || stdout);
                    resolve(errorResult);
                } catch {
                    reject(new Error(`Workflow failed: ${error.message}\n${stderr || stdout}`));
                }
                return;
            }

            try {
                // Extract JSON from output (may have other text before/after)
                const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                if (jsonMatch) {
                    const result = JSON.parse(jsonMatch[0]);
                    resolve(result);
                } else {
                    // If no JSON found, return raw output as error
                    reject(new Error(`No JSON output found:\n${stdout}`));
                }
            } catch (parseErr) {
                reject(new Error(`Failed to parse output: ${parseErr}\n${stdout}`));
            }
        });
    });
}

/**
 * Run meta-workflow with webview report (Quick Mode)
 */
export async function runMetaWorkflowWithReport(
    extensionUri: vscode.Uri,
    templateId?: string
): Promise<void> {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        vscode.window.showErrorMessage('Please open a workspace folder first.');
        return;
    }

    // If no template provided, show quick pick
    if (!templateId) {
        const templates = [
            {
                label: '🚀 Release Preparation',
                description: 'release-prep',
                detail: 'Security, testing, code quality, and docs (~$0.10-$0.75)'
            },
            {
                label: '🧪 Test Coverage Boost',
                description: 'test-coverage-boost',
                detail: 'Analyze gaps and generate tests (~$0.15-$1.00)'
            },
            {
                label: '🔧 Test Maintenance',
                description: 'test-maintenance',
                detail: 'Fix stale tests, lifecycle management (~$0.10-$0.80)'
            },
            {
                label: '📚 Documentation Management',
                description: 'manage-docs',
                detail: 'Sync docs with code, find gaps (~$0.08-$0.50)'
            },
            {
                label: '📝 Feature Overview',
                description: 'feature-overview',
                detail: 'Generate technical documentation (~$0.40-$0.80)'
            }
        ];

        const selected = await vscode.window.showQuickPick(templates, {
            placeHolder: 'Select a meta-workflow to run (uses defaults)',
            ignoreFocusOut: true
        });

        if (!selected) {
            return;
        }

        templateId = selected.description;
    }

    // Show running state in panel
    MetaWorkflowReportPanel.showRunning(extensionUri, templateId!);

    // Execute with progress notification
    try {
        const result = await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `Running meta-workflow: ${templateId}`,
            cancellable: false
        }, async (progress) => {
            progress.report({ message: 'Executing agents...' });
            return await executeMetaWorkflowJson(templateId!, true);
        });

        // Show result in panel
        MetaWorkflowReportPanel.showAfterExecution(extensionUri, result, templateId!);

        if (result.success) {
            vscode.window.showInformationMessage(`✅ Meta-workflow complete: ${templateId}`);
        } else {
            vscode.window.showWarningMessage(`⚠️ Meta-workflow completed with issues: ${templateId}`);
        }
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        vscode.window.showErrorMessage(`Meta-workflow failed: ${errorMessage}`);

        // Show error in panel
        MetaWorkflowReportPanel.showAfterExecution(extensionUri, {
            run_id: '',
            template_id: templateId!,
            timestamp: new Date().toISOString(),
            success: false,
            error: errorMessage,
            total_cost: 0,
            total_duration: 0,
            agents_created: 0,
            agent_results: []
        }, templateId!);
    }
}

/**
 * Show meta-workflow report panel for a specific run
 */
export async function showMetaWorkflowReport(extensionUri: vscode.Uri): Promise<void> {
    // Get list of recent runs and let user pick one
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        vscode.window.showErrorMessage('Please open a workspace folder first.');
        return;
    }

    let cwd = workspaceFolders[0].uri.fsPath;
    if (cwd.endsWith('vscode-extension')) {
        cwd = path.dirname(cwd);
    }

    // Get list of runs
    // v4.6.3: Use 'empathy' CLI directly
    const runs = await new Promise<string[]>((resolve) => {
        cp.execFile('empathy', ['meta-workflow', 'list-runs', '--json'], {
            cwd: cwd,
            maxBuffer: 1024 * 1024
        }, (error, stdout) => {
            if (error) {
                resolve([]);
                return;
            }
            try {
                const result = JSON.parse(stdout);
                resolve(result.runs || []);
            } catch {
                resolve([]);
            }
        });
    });

    if (runs.length === 0) {
        vscode.window.showInformationMessage('No meta-workflow runs found.');
        return;
    }

    const items = runs.slice(0, 10).map(runId => ({
        label: runId,
        description: runId.split('-').slice(0, -1).join('-')
    }));

    const selected = await vscode.window.showQuickPick(items, {
        placeHolder: 'Select a run to view'
    });

    if (selected) {
        MetaWorkflowReportPanel.createOrShow(extensionUri, selected.label);
    }
}

/**
 * List meta-workflow templates
 */
export async function listTemplates(): Promise<void> {
    vscode.window.showInformationMessage('Loading meta-workflow templates...');
    await executeCliCommand('meta-workflow', ['list-templates']);
}

/**
 * Inspect a meta-workflow template
 */
export async function inspectTemplate(): Promise<void> {
    // Show quick pick with known templates (v4.3.0 built-in templates)
    const templates = [
        { label: '🚀 Release Preparation', value: 'release-prep' },
        { label: '🧪 Test Coverage Boost', value: 'test-coverage-boost' },
        { label: '🔧 Test Maintenance', value: 'test-maintenance' },
        { label: '📚 Documentation Management', value: 'manage-docs' },
        { label: '⌨️  Custom Template (Enter ID)', value: '__custom__' }
    ];

    const selected = await vscode.window.showQuickPick(templates, {
        placeHolder: 'Select template to inspect',
        ignoreFocusOut: true
    });

    if (!selected) {
        return;
    }

    let templateId = selected.value;

    if (templateId === '__custom__') {
        const customId = await vscode.window.showInputBox({
            prompt: 'Enter template ID to inspect',
            placeHolder: 'e.g., my_custom_workflow',
            ignoreFocusOut: true
        });

        if (!customId) {
            return;
        }

        templateId = customId;
    }

    vscode.window.showInformationMessage(`Inspecting template: ${templateId}`);
    await executeCliCommand('meta-workflow', ['inspect', templateId]);
}

/**
 * Run a meta-workflow - offers choice between Interactive and Quick Run modes
 */
export async function runMetaWorkflow(extensionUri?: vscode.Uri): Promise<void> {
    console.log('[Empathy] runMetaWorkflow called');

    try {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            vscode.window.showErrorMessage('Empathy: Please open a workspace folder first.');
            return;
        }

        // First, ask for execution mode
        const modeOptions = [
            {
                label: '$(preview) Quick Run (Webview Report)',
                description: 'webview',
                detail: 'Uses default values, shows rich HTML report when complete'
            },
            {
                label: '$(terminal) Interactive Mode (Terminal)',
                description: 'terminal',
                detail: 'Answer form questions in terminal, see raw output'
            }
        ];

        const modeSelected = await vscode.window.showQuickPick(modeOptions, {
            placeHolder: 'Select execution mode',
            ignoreFocusOut: true
        });

        if (!modeSelected) {
            return;
        }

        // If webview mode selected, use the new function
        if (modeSelected.description === 'webview') {
            if (extensionUri) {
                await runMetaWorkflowWithReport(extensionUri);
            } else {
                // If no extensionUri passed, fall back to terminal mode
                vscode.window.showWarningMessage('Webview mode requires extension context. Falling back to terminal.');
                await runMetaWorkflowTerminal(workspaceFolders[0].uri.fsPath);
            }
            return;
        }

        // Terminal mode
        await runMetaWorkflowTerminal(workspaceFolders[0].uri.fsPath);

    } catch (error) {
        console.error('[Empathy] Error in runMetaWorkflow:', error);
        vscode.window.showErrorMessage(`Failed to run meta-workflow: ${error}`);
    }
}

/**
 * Run meta-workflow in terminal (Interactive Mode)
 */
async function runMetaWorkflowTerminal(workspacePath: string): Promise<void> {
    // Show quick pick with known templates
    const templates = [
        {
            label: '🚀 Release Preparation',
            description: 'release-prep',
            detail: 'Security, testing, code quality, and docs (~$0.10-$0.75)'
        },
        {
            label: '🧪 Test Coverage Boost',
            description: 'test-coverage-boost',
            detail: 'Analyze gaps and generate tests (~$0.15-$1.00)'
        },
        {
            label: '🔧 Test Maintenance',
            description: 'test-maintenance',
            detail: 'Fix stale tests, lifecycle management (~$0.10-$0.80)'
        },
        {
            label: '📚 Documentation Management',
            description: 'manage-docs',
            detail: 'Sync docs with code, find gaps (~$0.08-$0.50)'
        },
        {
            label: '📝 Feature Overview',
            description: 'feature-overview',
            detail: 'Generate technical documentation (~$0.40-$0.80)'
        },
        {
            label: '⌨️  Custom Template (Enter ID)',
            description: '__custom__',
            detail: 'Enter a custom template ID'
        }
    ];

    const selected = await vscode.window.showQuickPick(templates, {
        placeHolder: 'Select a meta-workflow template to run',
        ignoreFocusOut: true
    });

    if (!selected) {
        return;
    }

    let templateId = selected.description;

    // Handle custom template input
    if (templateId === '__custom__') {
        const customId = await vscode.window.showInputBox({
            prompt: 'Enter template ID',
            placeHolder: 'e.g., my_custom_workflow',
            ignoreFocusOut: true
        });

        if (!customId) {
            return;
        }

        templateId = customId;
    }

    // Execute in terminal for interactivity
    const terminal = vscode.window.createTerminal({
        name: 'Empathy Meta-Workflow',
        cwd: workspacePath
    });

    terminal.show();

    // Small delay to ensure terminal is ready
    await new Promise(resolve => setTimeout(resolve, 100));

    const command = `empathy meta-workflow run ${templateId} --real`;
    terminal.sendText(command);

    vscode.window.showInformationMessage(`✅ Started meta-workflow: ${templateId}`, 'View Terminal').then(selection => {
        if (selection === 'View Terminal') {
            terminal.show();
        }
    });
}

/**
 * Show meta-workflow analytics
 */
export async function showAnalytics(): Promise<void> {
    vscode.window.showInformationMessage('Loading meta-workflow analytics...');
    await executeCliCommand('meta-workflow', ['analytics']);
}

/**
 * List meta-workflow execution history
 */
export async function listRuns(): Promise<void> {
    vscode.window.showInformationMessage('Loading execution history...');
    await executeCliCommand('meta-workflow', ['list-runs']);
}

/**
 * Show meta-workflow session statistics
 */
export async function showSessionStats(): Promise<void> {
    vscode.window.showInformationMessage('Loading session statistics...');
    await executeCliCommand('meta-workflow', ['session-stats']);
}

/**
 * Register all meta-workflow commands
 */
export function registerMetaWorkflowCommands(context: vscode.ExtensionContext): void {
    const extensionUri = context.extensionUri;

    context.subscriptions.push(
        vscode.commands.registerCommand('empathy.metaWorkflow.listTemplates', listTemplates),
        vscode.commands.registerCommand('empathy.metaWorkflow.inspect', inspectTemplate),
        vscode.commands.registerCommand('empathy.metaWorkflow.run', () => runMetaWorkflow(extensionUri)),
        vscode.commands.registerCommand('empathy.metaWorkflow.runWithReport', (templateId?: string) =>
            runMetaWorkflowWithReport(extensionUri, templateId)
        ),
        vscode.commands.registerCommand('empathy.metaWorkflow.showReport', (runId?: string) =>
            runId ? MetaWorkflowReportPanel.createOrShow(extensionUri, runId) : showMetaWorkflowReport(extensionUri)
        ),
        vscode.commands.registerCommand('empathy.metaWorkflow.analytics', showAnalytics),
        vscode.commands.registerCommand('empathy.metaWorkflow.listRuns', listRuns),
        vscode.commands.registerCommand('empathy.metaWorkflow.sessionStats', showSessionStats)
    );
}
