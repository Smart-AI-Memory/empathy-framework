/**
 * Workflow Execution Service
 *
 * Handles dynamic workflow command registration and execution.
 * Provides Quick Pick menu for workflow selection and executes workflows via Python CLI.
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';
import { promisify } from 'util';
import { Workflow, WorkflowCategory } from '../types/workflow';
import { WorkflowDiscoveryService } from './WorkflowDiscoveryService';

const execFile = promisify(cp.execFile);

export class WorkflowExecutionService {
    private discoveryService: WorkflowDiscoveryService;
    private context: vscode.ExtensionContext;
    private registeredCommands: vscode.Disposable[] = [];

    constructor(context: vscode.ExtensionContext, discoveryService: WorkflowDiscoveryService) {
        this.context = context;
        this.discoveryService = discoveryService;
    }

    /**
     * Register all discovered workflows as VSCode commands
     */
    async registerWorkflowCommands(): Promise<void> {
        const workflows = await this.discoveryService.discoverWorkflows();

        // Dispose previous registrations
        this.registeredCommands.forEach(cmd => cmd.dispose());
        this.registeredCommands = [];

        let registeredCount = 0;
        let skippedCount = 0;

        // Register each workflow as a command
        for (const workflow of workflows) {
            const commandId = `empathy.workflow.${workflow.name}`;

            try {
                const disposable = vscode.commands.registerCommand(commandId, async () => {
                    await this.executeWorkflow(workflow);
                });

                this.registeredCommands.push(disposable);
                this.context.subscriptions.push(disposable);
                registeredCount++;
            } catch (error) {
                // Command already exists - skip it gracefully
                if (error instanceof Error && error.message.includes('already exists')) {
                    console.log(`[WorkflowExecution] Command ${commandId} already registered, skipping`);
                    skippedCount++;
                } else {
                    throw error;
                }
            }
        }

        console.log(`[WorkflowExecution] Registered ${registeredCount} workflow commands (${skippedCount} already existed)`);
    }

    /**
     * Show Quick Pick menu for workflow selection
     */
    async showWorkflowPicker(category?: WorkflowCategory): Promise<void> {
        let workflows = await this.discoveryService.discoverWorkflows();

        // Filter by category if provided
        if (category) {
            workflows = workflows.filter(w => w.category === category);
        }

        if (workflows.length === 0) {
            vscode.window.showInformationMessage('No workflows available');
            return;
        }

        // Create Quick Pick items
        const items: vscode.QuickPickItem[] = workflows.map(workflow => ({
            label: `$(${workflow.icon?.replace('$(', '').replace(')', '') || 'symbol-misc'}) ${workflow.name}`,
            description: workflow.description,
            detail: workflow.stages ? `Stages: ${workflow.stages.join(' → ')}` : undefined,
        }));

        // Show Quick Pick
        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: category
                ? `Select a ${category} workflow to run`
                : 'Select a workflow to run',
            matchOnDescription: true,
            matchOnDetail: true,
        });

        if (!selected) {
            return;
        }

        // Extract workflow name from label
        const workflowName = selected.label.split(' ')[1]; // Remove icon
        const workflow = workflows.find(w => w.name === workflowName);

        if (workflow) {
            await this.executeWorkflow(workflow);
        }
    }

    /**
     * Execute a workflow via Python CLI
     */
    async executeWorkflow(workflow: Workflow, input?: Record<string, unknown>): Promise<void> {
        const pythonPath = vscode.workspace.getConfiguration('empathy').get<string>('pythonPath') || 'python';
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder found');
            return;
        }

        // Show progress indicator
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `Running ${workflow.name}...`,
            cancellable: false,
        }, async (progress) => {
            try {
                // v4.6.3: Build command arguments for 'empathy' CLI
                const args = ['workflow', 'run', workflow.name];

                if (input) {
                    args.push('--input', JSON.stringify(input));
                }

                // Execute workflow using empathy CLI
                const { stdout, stderr } = await execFile('empathy', args, {
                    cwd: workspaceFolder,
                    timeout: 300000, // 5 minutes
                });

                // Show results
                if (stdout) {
                    await this.showWorkflowResults(workflow, stdout);
                }

                if (stderr) {
                    console.error(`[WorkflowExecution] ${workflow.name} stderr:`, stderr);
                }

                vscode.window.showInformationMessage(`✓ ${workflow.name} completed successfully`);
            } catch (error) {
                console.error(`[WorkflowExecution] ${workflow.name} failed:`, error);
                const errorMessage = error instanceof Error ? error.message : String(error);
                vscode.window.showErrorMessage(`✗ ${workflow.name} failed: ${errorMessage}`);
            }
        });
    }

    /**
     * Show workflow results in a webview or output channel
     */
    private async showWorkflowResults(workflow: Workflow, output: string): Promise<void> {
        // Try to parse as JSON for structured output
        try {
            const result = JSON.parse(output);

            // If result has a report field, show it in a markdown preview
            if (result.report) {
                await this.showMarkdownReport(workflow.name, result.report);
                return;
            }

            // Otherwise show formatted JSON
            const formattedJson = JSON.stringify(result, null, 2);
            await this.showTextOutput(workflow.name, formattedJson);
        } catch {
            // Not JSON, show as plain text
            await this.showTextOutput(workflow.name, output);
        }
    }

    /**
     * Show markdown report in a new editor
     */
    private async showMarkdownReport(workflowName: string, markdown: string): Promise<void> {
        const doc = await vscode.workspace.openTextDocument({
            content: markdown,
            language: 'markdown',
        });

        await vscode.window.showTextDocument(doc, {
            preview: true,
            viewColumn: vscode.ViewColumn.Beside,
        });

        // Execute markdown preview command
        await vscode.commands.executeCommand('markdown.showPreview', doc.uri);
    }

    /**
     * Show plain text output
     */
    private async showTextOutput(workflowName: string, text: string): Promise<void> {
        const doc = await vscode.workspace.openTextDocument({
            content: text,
            language: 'plaintext',
        });

        await vscode.window.showTextDocument(doc, {
            preview: true,
            viewColumn: vscode.ViewColumn.Beside,
        });
    }

    /**
     * Refresh workflow registrations
     */
    async refreshWorkflows(): Promise<void> {
        await this.discoveryService.refreshWorkflows();
        await this.registerWorkflowCommands();
        vscode.window.showInformationMessage('Workflows refreshed');
    }

    /**
     * Dispose all registered commands
     */
    dispose(): void {
        this.registeredCommands.forEach(cmd => cmd.dispose());
        this.registeredCommands = [];
    }
}
