/**
 * Test Generator Panel - Interactive Test Generation Wizard
 *
 * A 4-step wizard for generating tests:
 * 1. Select Target - Choose file/folder to scan
 * 2. Review Candidates - See files needing tests with priority scores
 * 3. Select Functions/Classes - Pick specific targets from AST analysis
 * 4. Preview & Apply - Review generated pytest code and apply to files
 *
 * Copyright 2025 Smart-AI-Memory
 * Licensed under Fair Source License 0.9
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as cp from 'child_process';
import {
    getFilePickerService,
    createFilePickerMessageHandler,
    FilePickerService,
    FilePickerResponse,
    FILE_FILTERS
} from '../services/FilePickerService';

// =============================================================================
// Types
// =============================================================================

interface TestCandidate {
    file: string;
    lines: number;
    is_hotspot: boolean;
    has_tests: boolean;
    priority: number;
}

interface FunctionAnalysis {
    name: string;
    params: [string, string, string | null][];
    param_names: string[];
    is_async: boolean;
    return_type: string | null;
    raises: string[];
    has_side_effects: boolean;
    complexity: number;
    docstring: string | null;
}

interface ClassAnalysis {
    name: string;
    init_params: [string, string, string | null][];
    methods: { name: string; params: [string, string, string | null][]; is_async: boolean; raises: string[] }[];
    base_classes: string[];
    docstring: string | null;
}

interface FileAnalysis {
    file: string;
    priority: number;
    functions: FunctionAnalysis[];
    classes: ClassAnalysis[];
    function_count: number;
    class_count: number;
    test_suggestions: string[];
}

interface GeneratedTest {
    target: string;
    type: 'function' | 'class';
    code: string;
}

interface GeneratedTestFile {
    source_file: string;
    test_file: string;
    tests: GeneratedTest[];
    test_count: number;
}

interface TestGenSession {
    sessionId: string;
    stage: 'idle' | 'scanning' | 'analyzing' | 'selecting' | 'generating' | 'preview';
    targetPath: string;
    candidates: TestCandidate[];
    analysis: FileAnalysis[];
    selectedFiles: Set<string>;
    selectedTargets: Map<string, Set<string>>;
    generatedTests: GeneratedTestFile[];
    appliedTests: string[];
}

interface BackendHealth {
    status: 'ok' | 'degraded' | 'unknown';
    lastSuccessTime: number | null;
    lastErrorTime: number | null;
    consecutiveFailures: number;
    lastError: string | null;
}

// =============================================================================
// Utility Functions
// =============================================================================

function getNonce(): string {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}

function generateUUID(): string {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// =============================================================================
// TestGeneratorPanel Class - Editor Panel (opens in main editor area)
// =============================================================================

export class TestGeneratorPanel {
    public static currentPanel: TestGeneratorPanel | undefined;

    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _session: TestGenSession | null = null;
    private _disposables: vscode.Disposable[] = [];
    private _activeProcess: cp.ChildProcess | null = null;
    private _filePickerService: FilePickerService;
    private _handleFilePicker: ((message: any) => Promise<boolean>) | null = null;
    private _backendHealth: BackendHealth = {
        status: 'unknown',
        lastSuccessTime: null,
        lastErrorTime: null,
        consecutiveFailures: 0,
        lastError: null,
    };

    /**
     * Create or reveal the Test Generator panel
     */
    public static createOrShow(extensionUri: vscode.Uri): TestGeneratorPanel {
        const column = vscode.window.activeTextEditor?.viewColumn || vscode.ViewColumn.One;

        // If panel already exists, reveal it and reset to initial state
        if (TestGeneratorPanel.currentPanel) {
            TestGeneratorPanel.currentPanel._panel.reveal(column);
            // Reset session so user can start fresh
            TestGeneratorPanel.currentPanel._resetSession();
            TestGeneratorPanel.currentPanel._panel.webview.postMessage({ type: 'sessionReset' });
            return TestGeneratorPanel.currentPanel;
        }

        // Create new panel
        const panel = vscode.window.createWebviewPanel(
            'empathyTestGenerator',
            'Test Generator',
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [extensionUri]
            }
        );

        TestGeneratorPanel.currentPanel = new TestGeneratorPanel(panel, extensionUri);
        return TestGeneratorPanel.currentPanel;
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._filePickerService = getFilePickerService();

        // Set initial HTML
        this._panel.webview.html = this._getHtmlForWebview(this._panel.webview);

        // Handle panel disposal
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Set up file picker message handler
        this._handleFilePicker = createFilePickerMessageHandler(
            this._filePickerService,
            (msg: FilePickerResponse) => {
                // Convert filePicker:result to pathSelected for compatibility
                if (msg.type === 'filePicker:result' && msg.success && msg.result) {
                    const result = Array.isArray(msg.result) ? msg.result[0] : msg.result;
                    this._panel.webview.postMessage({
                        type: 'pathSelected',
                        path: result.path,
                        isDirectory: result.isDirectory
                    });
                } else if (!msg.success && msg.error) {
                    this._sendError(msg.error);
                }
            }
        );

        // Handle messages from webview
        this._panel.webview.onDidReceiveMessage(
            message => this._handleMessage(message),
            null,
            this._disposables
        );

        // Track active file changes
        this._disposables.push(
            vscode.window.onDidChangeActiveTextEditor(editor => {
                this._sendActiveFile(editor);
            })
        );

        // Send initial active file
        this._sendActiveFile(vscode.window.activeTextEditor);

        // Pre-fill with project root
        this._sendProjectRoot();
    }

    private _sendProjectRoot(): void {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (workspaceFolder) {
            this._panel.webview.postMessage({
                type: 'pathSelected',
                path: workspaceFolder,
                isDirectory: true
            });
        }
    }

    private _sendActiveFile(editor: vscode.TextEditor | undefined): void {
        if (editor) {
            const fileName = path.basename(editor.document.uri.fsPath);
            this._panel.webview.postMessage({
                type: 'activeFileChanged',
                fileName,
                filePath: editor.document.uri.fsPath
            });
        } else {
            this._panel.webview.postMessage({
                type: 'activeFileChanged',
                fileName: null
            });
        }
    }

    public dispose() {
        TestGeneratorPanel.currentPanel = undefined;

        if (this._activeProcess) {
            this._activeProcess.kill();
        }

        this._panel.dispose();

        while (this._disposables.length) {
            const disposable = this._disposables.pop();
            if (disposable) {
                disposable.dispose();
            }
        }
    }

    private async _handleMessage(message: any) {
        // Route file picker messages through the service
        if (message.type?.startsWith('filePicker:')) {
            await this._handleFilePicker?.(message);
            return;
        }

        switch (message.type) {
            case 'scanWorkspace':
                await this._scanWorkspace(message.targetPath);
                break;
            case 'selectFile':
                this._selectFile(message.file, message.selected);
                break;
            case 'selectTarget':
                this._selectTarget(message.file, message.target, message.selected);
                break;
            case 'selectAllInFile':
                this._selectAllInFile(message.file, message.selected);
                break;
            case 'analyzeSelected':
                await this._analyzeSelected();
                break;
            case 'generateTests':
                await this._generateTests();
                break;
            case 'applyTest':
                await this._applyTest(message.sourceFile, message.testIndex);
                break;
            case 'applyAllSelected':
                await this._applyAllSelected();
                break;
            case 'cancelOperation':
                this._cancelOperation();
                break;
            case 'resetSession':
                this._resetSession();
                break;
            case 'getSessionState':
                this._sendSessionState();
                this._sendHealthStatus();
                break;
            case 'goBack':
                this._goBack(message.fromStage);
                break;
        }
    }

    // =========================================================================
    // Workflow Stage Methods
    // =========================================================================

    private async _scanWorkspace(targetPath: string): Promise<void> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            this._sendError('No workspace folder open');
            return;
        }

        // Preflight check
        const preflight = await this._preflightCheck();
        if (!preflight.ok) {
            this._sendError(preflight.error || 'Preflight check failed');
            return;
        }

        // Initialize session
        this._session = {
            sessionId: generateUUID(),
            stage: 'scanning',
            targetPath,
            candidates: [],
            analysis: [],
            selectedFiles: new Set(),
            selectedTargets: new Map(),
            generatedTests: [],
            appliedTests: []
        };

        this._panel.webview.postMessage({ type: 'scanning', targetPath });

        // Get configurable limits from settings with sensible defaults
        const testGenConfig = vscode.workspace.getConfiguration('empathy.testGen');
        const inputData = {
            path: targetPath,
            file_types: ['.py'],
            // Configurable limits - users can override in settings
            max_files_to_scan: testGenConfig.get<number>('maxFilesToScan', 1000),
            max_file_size_kb: testGenConfig.get<number>('maxFileSizeKb', 200),
            max_candidates: testGenConfig.get<number>('maxCandidates', 50),
            max_files_to_analyze: testGenConfig.get<number>('maxFilesToAnalyze', 20),
            max_functions_per_file: testGenConfig.get<number>('maxFunctionsPerFile', 30),
            max_classes_per_file: testGenConfig.get<number>('maxClassesPerFile', 15),
            max_files_to_generate: testGenConfig.get<number>('maxFilesToGenerate', 15),
            max_functions_to_generate: testGenConfig.get<number>('maxFunctionsToGenerate', 8),
            max_classes_to_generate: testGenConfig.get<number>('maxClassesToGenerate', 4),
            include_all_files: testGenConfig.get<boolean>('includeAllFiles', false),
        };

        // Run test-gen workflow identify stage
        // v4.6.3: Use 'empathy' CLI directly
        const args = [
            'workflow', 'run', 'test-gen',
            '--input', JSON.stringify(inputData),
            '--json'
        ];

        this._activeProcess = cp.execFile('empathy', args, {
            cwd: workspaceFolder,
            maxBuffer: 5 * 1024 * 1024,
            timeout: 120000
        }, (error, stdout, stderr) => {
            this._activeProcess = null;

            if (error) {
                this._recordBackendFailure(error.message);
                this._sendError(`Scan failed: ${error.message}`);
                return;
            }

            this._recordBackendSuccess();

            try {
                const output = JSON.parse(stdout);
                // The workflow returns final_output which contains candidates from identify stage
                const finalOutput = output.final_output || output;
                const candidates = finalOutput.candidates || [];

                // Extract scan summary for visibility
                const scanSummary = finalOutput.scan_summary || {};
                const parseErrors = finalOutput.parse_errors || [];

                if (this._session) {
                    this._session.candidates = candidates;
                    this._session.stage = 'selecting';
                    // Auto-select high priority files
                    candidates.forEach((c: TestCandidate) => {
                        if (c.priority >= 50 || c.is_hotspot) {
                            this._session?.selectedFiles.add(c.file);
                        }
                    });
                }

                const hotspots = candidates.filter((c: TestCandidate) => c.is_hotspot).length;
                const untested = candidates.filter((c: TestCandidate) => !c.has_tests).length;

                this._panel.webview.postMessage({
                    type: 'candidates',
                    candidates,
                    summary: {
                        total: candidates.length,
                        hotspots,
                        untested,
                        // Include scan summary for UI display
                        scanSummary: {
                            filesScanned: scanSummary.files_scanned || 0,
                            filesTooLarge: scanSummary.files_too_large || 0,
                            filesReadError: scanSummary.files_read_error || 0,
                            filesExcluded: scanSummary.files_excluded_by_pattern || 0,
                            earlyExitReason: scanSummary.early_exit_reason || null,
                        },
                        parseErrors: parseErrors.slice(0, 5), // Limit to 5 errors for UI
                        totalSourceFiles: finalOutput.total_source_files || 0,
                        existingTestFiles: finalOutput.existing_test_files || 0,
                    }
                });
            } catch (parseErr) {
                this._sendError('Failed to parse scan results');
                console.error('Parse error:', parseErr, 'stdout:', stdout);
            }
        });
    }

    private async _analyzeSelected(): Promise<void> {
        if (!this._session || this._session.selectedFiles.size === 0) {
            this._sendError('No files selected for analysis');
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) return;

        this._session.stage = 'analyzing';
        const selectedFiles = Array.from(this._session.selectedFiles);

        this._panel.webview.postMessage({ type: 'analyzing', files: selectedFiles });

        // Run test-gen workflow with analyze stage focus
        // v4.6.3: Use 'empathy' CLI directly
        const args = [
            'workflow', 'run', 'test-gen',
            '--input', JSON.stringify({
                path: this._session.targetPath,
                files: selectedFiles,
                file_types: ['.py']
            }),
            '--json'
        ];

        this._activeProcess = cp.execFile('empathy', args, {
            cwd: workspaceFolder,
            maxBuffer: 5 * 1024 * 1024,
            timeout: 180000
        }, (error, stdout, stderr) => {
            this._activeProcess = null;

            if (error) {
                this._recordBackendFailure(error.message);
                this._sendError(`Analysis failed: ${error.message}`);
                return;
            }

            this._recordBackendSuccess();

            try {
                const output = JSON.parse(stdout);
                const analysis = output.final_output?.analysis || output.analysis || [];

                if (this._session) {
                    this._session.analysis = analysis;
                    this._session.stage = 'selecting';

                    // Auto-select all functions/classes
                    analysis.forEach((a: FileAnalysis) => {
                        const targets = new Set<string>();
                        a.functions.forEach(f => targets.add(f.name));
                        a.classes.forEach(c => targets.add(c.name));
                        this._session?.selectedTargets.set(a.file, targets);
                    });
                }

                const totalFunctions = analysis.reduce((sum: number, a: FileAnalysis) => sum + a.function_count, 0);
                const totalClasses = analysis.reduce((sum: number, a: FileAnalysis) => sum + a.class_count, 0);

                this._panel.webview.postMessage({
                    type: 'analysis',
                    analysis,
                    totals: { functions: totalFunctions, classes: totalClasses }
                });
            } catch (parseErr) {
                this._sendError('Failed to parse analysis results');
                console.error('Parse error:', parseErr);
            }
        });
    }

    private async _generateTests(): Promise<void> {
        if (!this._session || this._session.selectedTargets.size === 0) {
            this._sendError('No targets selected for test generation');
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) return;

        this._session.stage = 'generating';

        // Build targets list for display
        const targetsList: { file: string; targets: string[] }[] = [];
        this._session.selectedTargets.forEach((targets, file) => {
            targetsList.push({ file, targets: Array.from(targets) });
        });

        this._panel.webview.postMessage({ type: 'generating', targets: targetsList });

        // Run full test-gen workflow
        // v4.6.3: Use 'empathy' CLI directly
        const args = [
            'workflow', 'run', 'test-gen',
            '--input', JSON.stringify({
                path: this._session.targetPath,
                file_types: ['.py']
            }),
            '--json'
        ];

        this._activeProcess = cp.execFile('empathy', args, {
            cwd: workspaceFolder,
            maxBuffer: 10 * 1024 * 1024,
            timeout: 300000 // 5 minutes for generation
        }, (error, stdout, stderr) => {
            this._activeProcess = null;

            if (error) {
                this._recordBackendFailure(error.message);
                this._sendError(`Test generation failed: ${error.message}`);
                return;
            }

            this._recordBackendSuccess();

            try {
                const output = JSON.parse(stdout);
                const generatedTests = output.final_output?.generated_tests || output.generated_tests || [];

                if (this._session) {
                    this._session.generatedTests = generatedTests;
                    this._session.stage = 'preview';
                }

                const totalTests = generatedTests.reduce((sum: number, g: GeneratedTestFile) => sum + g.test_count, 0);

                this._panel.webview.postMessage({
                    type: 'generated',
                    tests: generatedTests,
                    totalTests
                });
            } catch (parseErr) {
                this._sendError('Failed to parse generated tests');
                console.error('TestGeneratorPanel: Parse error', parseErr);
            }
        });
    }

    private async _applyTest(sourceFile: string, testIndex: number): Promise<void> {
        if (!this._session) {
            this._sendError('No active session');
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            this._sendError('No workspace folder open');
            return;
        }

        const testFile = this._session.generatedTests.find(t => t.source_file === sourceFile);
        if (!testFile || !testFile.tests[testIndex]) {
            this._sendError('Test not found');
            return;
        }

        const test = testFile.tests[testIndex];
        const testFilePath = this._resolveTestFilePath(workspaceFolder, sourceFile, testFile.test_file);

        try {
            // Ensure parent directory exists
            const parentDir = path.dirname(testFilePath);
            if (!fs.existsSync(parentDir)) {
                fs.mkdirSync(parentDir, { recursive: true });
            }

            let existingContent = '';
            if (fs.existsSync(testFilePath)) {
                existingContent = fs.readFileSync(testFilePath, 'utf8');
            }

            // Append test to file
            const newContent = existingContent
                ? `${existingContent}\n\n${test.code}`
                : test.code;

            fs.writeFileSync(testFilePath, newContent);
            this._session.appliedTests.push(testFilePath);

            this._panel.webview.postMessage({
                type: 'testApplied',
                testFile: testFilePath,
                sourceFile,
                testIndex,
                success: true
            });

            vscode.window.showInformationMessage(`Test applied to ${path.basename(testFilePath)}`);
        } catch (err) {
            const errorMsg = (err as Error).message;
            this._panel.webview.postMessage({
                type: 'testApplied',
                testFile: testFilePath,
                sourceFile,
                testIndex,
                success: false,
                error: errorMsg
            });
            vscode.window.showErrorMessage(`Failed to apply test: ${errorMsg}`);
        }
    }

    private async _applyAllSelected(): Promise<void> {
        if (!this._session) {
            this._sendError('No active session');
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            this._sendError('No workspace folder open');
            return;
        }

        if (!this._session.generatedTests || this._session.generatedTests.length === 0) {
            this._sendError('No tests have been generated yet');
            return;
        }

        let applied = 0;
        let failed = 0;

        for (const testFile of this._session.generatedTests) {
            const testFilePath = this._resolveTestFilePath(workspaceFolder, testFile.source_file, testFile.test_file);

            try {
                // Ensure parent directory exists
                const parentDir = path.dirname(testFilePath);
                if (!fs.existsSync(parentDir)) {
                    fs.mkdirSync(parentDir, { recursive: true });
                }

                let existingContent = '';
                if (fs.existsSync(testFilePath)) {
                    existingContent = fs.readFileSync(testFilePath, 'utf8');
                }

                // Combine all tests for this file
                const allTestCode = testFile.tests.map((t: GeneratedTest) => t.code).join('\n\n');

                const newContent = existingContent
                    ? `${existingContent}\n\n${allTestCode}`
                    : allTestCode;

                fs.writeFileSync(testFilePath, newContent);
                this._session.appliedTests.push(testFilePath);
                applied++;
            } catch (err) {
                failed++;
                console.error('TestGeneratorPanel: Failed to apply test', testFilePath, err);
            }
        }

        this._panel.webview.postMessage({
            type: 'allTestsApplied',
            applied,
            failed
        });

        if (applied > 0) {
            vscode.window.showInformationMessage(`Applied ${applied} test file(s)`);
        }
        if (failed > 0) {
            vscode.window.showWarningMessage(`Failed to apply ${failed} test file(s)`);
        }
    }

    // =========================================================================
    // Selection Methods
    // =========================================================================

    private _selectFile(file: string, selected: boolean): void {
        if (!this._session) return;

        if (selected) {
            this._session.selectedFiles.add(file);
        } else {
            this._session.selectedFiles.delete(file);
        }
    }

    private _selectTarget(file: string, target: string, selected: boolean): void {
        if (!this._session) return;

        if (!this._session.selectedTargets.has(file)) {
            this._session.selectedTargets.set(file, new Set());
        }

        const targets = this._session.selectedTargets.get(file)!;
        if (selected) {
            targets.add(target);
        } else {
            targets.delete(target);
        }
    }

    private _selectAllInFile(file: string, selected: boolean): void {
        if (!this._session) return;

        const fileAnalysis = this._session.analysis.find(a => a.file === file);
        if (!fileAnalysis) return;

        if (selected) {
            const targets = new Set<string>();
            fileAnalysis.functions.forEach(f => targets.add(f.name));
            fileAnalysis.classes.forEach(c => targets.add(c.name));
            this._session.selectedTargets.set(file, targets);
        } else {
            this._session.selectedTargets.delete(file);
        }
    }

    // =========================================================================
    // Helper Methods
    // =========================================================================

    private _resolveTestFilePath(workspaceFolder: string, sourceFile: string, testFileName: string): string {
        const sourcePath = path.parse(sourceFile);
        const sourceDir = path.join(workspaceFolder, sourcePath.dir);

        // Check common test locations in order
        const possibleLocations = [
            path.join(sourceDir, testFileName),
            path.join(sourceDir, 'tests', testFileName),
            path.join(workspaceFolder, 'tests', testFileName),
        ];

        // If existing test file found, use that location
        for (const loc of possibleLocations) {
            if (fs.existsSync(loc)) {
                return loc;
            }
        }

        // Default: create in same directory as source
        return possibleLocations[0];
    }

    private async _preflightCheck(): Promise<{ ok: boolean; error?: string }> {
        const config = vscode.workspace.getConfiguration('empathy');
        const pythonPath = config.get<string>('pythonPath', 'python');

        return new Promise((resolve) => {
            cp.execFile(pythonPath, ['--version'], { timeout: 5000 }, (error) => {
                if (error) {
                    resolve({ ok: false, error: `Python not found: ${error.message}` });
                    return;
                }
                resolve({ ok: true });
            });
        });
    }

    private _recordBackendSuccess(): void {
        this._backendHealth.status = 'ok';
        this._backendHealth.lastSuccessTime = Date.now();
        this._backendHealth.consecutiveFailures = 0;
        this._backendHealth.lastError = null;
        this._sendHealthStatus();
    }

    private _recordBackendFailure(error: string): void {
        this._backendHealth.lastErrorTime = Date.now();
        this._backendHealth.consecutiveFailures++;
        this._backendHealth.lastError = error;
        if (this._backendHealth.consecutiveFailures >= 2) {
            this._backendHealth.status = 'degraded';
        }
        this._sendHealthStatus();
    }

    private _sendHealthStatus(): void {
        this._panel.webview.postMessage({
            type: 'healthStatus',
            health: this._backendHealth
        });
    }

    private _sendSessionState(): void {
        if (this._session) {
            this._panel.webview.postMessage({
                type: 'sessionState',
                session: {
                    ...this._session,
                    selectedFiles: Array.from(this._session.selectedFiles),
                    selectedTargets: Object.fromEntries(
                        Array.from(this._session.selectedTargets.entries()).map(
                            ([k, v]) => [k, Array.from(v)]
                        )
                    )
                }
            });
        }
    }

    private _sendError(message: string): void {
        this._panel.webview.postMessage({ type: 'error', message });
        vscode.window.showErrorMessage(`Test Generator: ${message}`);
    }

    private _cancelOperation(): void {
        if (this._activeProcess) {
            this._activeProcess.kill();
            this._activeProcess = null;
            this._panel.webview.postMessage({ type: 'operationCancelled' });
            vscode.window.showInformationMessage('Operation cancelled');
        }
    }

    private _resetSession(): void {
        this._session = null;
        this._panel.webview.postMessage({ type: 'sessionReset' });
    }

    private _goBack(fromStage: string): void {
        if (!this._session) return;

        switch (fromStage) {
            case 'candidates':
                this._session.stage = 'idle';
                this._session.candidates = [];
                break;
            case 'analysis':
                this._session.stage = 'selecting';
                this._session.analysis = [];
                this._session.selectedTargets.clear();
                break;
            case 'preview':
                this._session.stage = 'selecting';
                this._session.generatedTests = [];
                break;
        }

        this._sendSessionState();
    }

    // =========================================================================
    // WebView HTML
    // =========================================================================

    private _getHtmlForWebview(webview: vscode.Webview): string {
        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <title>Test Generator</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background: var(--vscode-sideBar-background);
            padding: 12px;
        }
        .hidden { display: none !important; }

        /* Health Indicator */
        .health-indicator {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            border-radius: 4px;
            margin-bottom: 12px;
            font-size: 11px;
        }
        .health-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        .health-ok { background: rgba(34, 197, 94, 0.1); }
        .health-ok .health-dot { background: #22c55e; }
        .health-degraded { background: rgba(234, 179, 8, 0.1); }
        .health-degraded .health-dot { background: #eab308; }
        .health-unknown { background: rgba(148, 163, 184, 0.1); }
        .health-unknown .health-dot { background: #94a3b8; }

        /* Sections */
        .section { margin-bottom: 16px; }
        h2 {
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 10px;
            color: var(--vscode-foreground);
        }

        /* Card */
        .card {
            background: var(--vscode-input-background);
            border: 1px solid var(--vscode-input-border);
            border-radius: 6px;
            padding: 12px;
        }

        /* Input Group */
        .input-group {
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
        }
        .input {
            flex: 1;
            padding: 6px 10px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 4px;
            font-size: 12px;
        }
        .input:read-only {
            background: var(--vscode-input-background);
            opacity: 0.8;
        }

        /* Buttons */
        .button-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }
        .button {
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        .button:hover { background: var(--vscode-button-hoverBackground); }
        .button:disabled { opacity: 0.5; cursor: not-allowed; }
        .button-secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }
        .button-secondary:hover { background: var(--vscode-button-secondaryHoverBackground); }
        .button-success {
            background: #22c55e;
            color: white;
        }
        .button-success:hover { background: #16a34a; }

        /* Stats Bar */
        .stats-bar {
            display: flex;
            gap: 12px;
            padding: 8px 12px;
            background: var(--vscode-input-background);
            border-radius: 4px;
            margin-bottom: 12px;
            font-size: 11px;
        }
        .stat { display: flex; align-items: center; gap: 4px; }
        .stat-value { font-weight: 600; }

        /* List Items */
        .scrollable-list {
            max-height: 250px;
            overflow-y: auto;
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px;
            margin-bottom: 12px;
        }
        .list-item {
            display: flex;
            align-items: center;
            padding: 8px 10px;
            border-bottom: 1px solid var(--vscode-input-border);
            cursor: pointer;
        }
        .list-item:last-child { border-bottom: none; }
        .list-item:hover { background: var(--vscode-list-hoverBackground); }
        .list-item.selected { background: var(--vscode-list-activeSelectionBackground); }
        .list-item input[type="checkbox"] { margin-right: 8px; }
        .list-item-content { flex: 1; }
        .list-item-title { font-size: 12px; }
        .list-item-meta { font-size: 10px; color: var(--vscode-descriptionForeground); }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: 500;
            margin-left: 6px;
        }
        .badge-hotspot { background: #ef4444; color: white; }
        .badge-priority { background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }
        .badge-async { background: #8b5cf6; color: white; }
        .badge-complexity { background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }

        /* Tree View */
        .tree-view { margin-bottom: 12px; }
        .tree-file {
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px;
            margin-bottom: 8px;
        }
        .tree-file-header {
            display: flex;
            align-items: center;
            padding: 8px 10px;
            background: var(--vscode-input-background);
            cursor: pointer;
        }
        .tree-file-header:hover { background: var(--vscode-list-hoverBackground); }
        .tree-arrow { margin-right: 6px; transition: transform 0.2s; }
        .tree-arrow.expanded { transform: rotate(90deg); }
        .tree-items { padding: 4px 0; }
        .tree-item {
            display: flex;
            align-items: center;
            padding: 4px 10px 4px 28px;
        }
        .tree-item:hover { background: var(--vscode-list-hoverBackground); }
        .tree-item input[type="checkbox"] { margin-right: 8px; }
        .tree-item-name { flex: 1; font-family: var(--vscode-editor-font-family); font-size: 12px; }

        /* Code Preview */
        .preview-container { margin-bottom: 12px; }
        .preview-file {
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px;
            margin-bottom: 8px;
        }
        .preview-file-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 10px;
            background: var(--vscode-input-background);
            border-bottom: 1px solid var(--vscode-input-border);
        }
        .preview-file-name { font-weight: 500; }
        .preview-test {
            padding: 8px;
            border-bottom: 1px solid var(--vscode-input-border);
        }
        .preview-test:last-child { border-bottom: none; }
        .preview-test-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 6px;
        }
        .preview-test-name { font-size: 11px; font-weight: 500; }
        .preview-code {
            background: var(--vscode-editor-background);
            border-radius: 4px;
            padding: 8px;
            font-family: var(--vscode-editor-font-family);
            font-size: 11px;
            line-height: 1.4;
            overflow-x: auto;
            white-space: pre;
            max-height: 200px;
            overflow-y: auto;
        }

        /* Syntax Highlighting */
        .keyword { color: var(--vscode-symbolIcon-keywordForeground, #569cd6); }
        .string { color: var(--vscode-symbolIcon-stringForeground, #ce9178); }
        .number { color: var(--vscode-symbolIcon-numberForeground, #b5cea8); }
        .comment { color: var(--vscode-symbolIcon-commentForeground, #6a9955); }
        .function { color: var(--vscode-symbolIcon-functionForeground, #dcdcaa); }
        .decorator { color: var(--vscode-symbolIcon-eventForeground, #c586c0); }

        /* Loading */
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            gap: 10px;
        }
        .spinner {
            width: 20px;
            height: 20px;
            border: 2px solid var(--vscode-input-border);
            border-top-color: var(--vscode-button-background);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 20px;
            color: var(--vscode-descriptionForeground);
        }
    </style>
</head>
<body>
    <!-- Health Indicator -->
    <div id="health-indicator" class="health-indicator health-unknown">
        <span class="health-dot"></span>
        <span id="health-text">Backend: Checking...</span>
    </div>

    <!-- Current File Indicator -->
    <div id="current-file" class="section" style="padding: 8px 12px; background: var(--vscode-editor-background); border-radius: 4px; margin-bottom: 12px; font-size: 11px;">
        <span style="color: var(--vscode-descriptionForeground);">Active file:</span>
        <span id="active-file-name" style="color: var(--vscode-textLink-foreground); margin-left: 4px;">None</span>
    </div>

    <!-- Step 1: Target Selection -->
    <div id="step-target" class="section">
        <h2>Test Generator Wizard</h2>
        <div class="card">
            <p style="margin-bottom: 10px; font-size: 12px; color: var(--vscode-descriptionForeground);">
                Select a file or folder to scan for test generation opportunities.
            </p>
            <div class="input-group">
                <input type="text" id="target-path" class="input" placeholder="Select a path..." readonly>
            </div>
            <div class="button-row">
                <button class="button button-secondary" id="btn-browse-file">File</button>
                <button class="button button-secondary" id="btn-browse-folder">Folder</button>
                <button class="button button-secondary" id="btn-active">Active</button>
                <button class="button button-secondary" id="btn-project">Project</button>
            </div>
            <button class="button" id="btn-scan" disabled>Scan for Candidates</button>
        </div>
    </div>

    <!-- Loading State -->
    <div id="loading" class="section hidden">
        <div class="loading">
            <div class="spinner"></div>
            <span id="loading-text">Scanning...</span>
        </div>
        <div id="loading-timeout" class="hidden" style="text-align: center; color: var(--vscode-errorForeground); margin-bottom: 10px;">
            ⚠️ Operation taking longer than expected...
        </div>
        <div style="text-align: center; display: flex; gap: 8px; justify-content: center;">
            <button class="button button-secondary" id="btn-cancel">Cancel</button>
            <button class="button button-secondary" id="btn-reset" title="Reset wizard to start over">Reset</button>
        </div>
    </div>

    <!-- Step 2: Candidates -->
    <div id="step-candidates" class="section hidden">
        <div class="stats-bar">
            <div class="stat"><span id="stat-total" class="stat-value">0</span> files</div>
            <div class="stat"><span id="stat-hotspots" class="stat-value">0</span> hotspots</div>
            <div class="stat"><span id="stat-untested" class="stat-value">0</span> untested</div>
        </div>
        <h2>Files Needing Tests</h2>
        <div id="candidates-list" class="scrollable-list"></div>
        <div class="button-row">
            <button class="button button-secondary" id="btn-back-target">Back</button>
            <button class="button" id="btn-analyze">Analyze Selected</button>
        </div>
    </div>

    <!-- Step 3: Analysis & Selection -->
    <div id="step-analysis" class="section hidden">
        <div class="stats-bar">
            <div class="stat"><span id="stat-functions" class="stat-value">0</span> functions</div>
            <div class="stat"><span id="stat-classes" class="stat-value">0</span> classes</div>
        </div>
        <h2>Select Functions/Classes</h2>
        <div id="analysis-tree" class="tree-view"></div>
        <div class="button-row">
            <button class="button button-secondary" id="btn-back-candidates">Back</button>
            <button class="button" id="btn-generate">Generate Tests</button>
        </div>
    </div>

    <!-- Step 4: Preview & Apply -->
    <div id="step-preview" class="section hidden">
        <div class="stats-bar">
            <div class="stat"><span id="stat-tests" class="stat-value">0</span> tests generated</div>
        </div>
        <h2>Preview & Apply Tests</h2>
        <div id="test-preview" class="preview-container"></div>
        <div class="button-row">
            <button class="button button-secondary" id="btn-back-analysis">Back</button>
            <button class="button button-success" id="btn-apply-all">Apply All</button>
        </div>
    </div>

    <script nonce="${nonce}">
        const vscode = acquireVsCodeApi();

        // State
        let targetPath = '';
        let candidates = [];
        let analysis = [];
        let generatedTests = [];
        let selectedFiles = new Set();
        let selectedTargets = {};
        let loadingTimeoutId = null;

        // Elements
        const stepTarget = document.getElementById('step-target');
        const stepCandidates = document.getElementById('step-candidates');
        const stepAnalysis = document.getElementById('step-analysis');
        const stepPreview = document.getElementById('step-preview');
        const loading = document.getElementById('loading');
        const loadingText = document.getElementById('loading-text');
        const targetInput = document.getElementById('target-path');

        // Button handlers - using standardized filePicker:* message types
        document.getElementById('btn-browse-file').addEventListener('click', () => {
            vscode.postMessage({
                type: 'filePicker:selectFile',
                options: { filters: { 'Python Files': ['py'] }, title: 'Select Python file' }
            });
        });
        document.getElementById('btn-browse-folder').addEventListener('click', () => {
            vscode.postMessage({
                type: 'filePicker:selectFolder',
                options: { title: 'Select folder for test generation' }
            });
        });
        document.getElementById('btn-active').addEventListener('click', () => {
            vscode.postMessage({
                type: 'filePicker:useActiveFile',
                options: { languageFilter: 'python' }
            });
        });
        document.getElementById('btn-project').addEventListener('click', () => {
            vscode.postMessage({ type: 'filePicker:useProjectRoot' });
        });
        document.getElementById('btn-scan').addEventListener('click', () => {
            if (targetPath) {
                vscode.postMessage({ type: 'scanWorkspace', targetPath });
            }
        });
        document.getElementById('btn-cancel').addEventListener('click', () => {
            vscode.postMessage({ type: 'cancelOperation' });
        });
        document.getElementById('btn-reset').addEventListener('click', () => {
            // Hard reset - clear all state and go back to start
            clearTimeout(loadingTimeoutId);
            loadingTimeoutId = null;
            targetPath = '';
            candidates = [];
            analysis = [];
            generatedTests = [];
            selectedFiles = new Set();
            selectedTargets = {};
            targetInput.value = '';
            document.getElementById('btn-scan').disabled = true;
            document.getElementById('loading-timeout').classList.add('hidden');
            vscode.postMessage({ type: 'resetSession' });
            showStep('target');
        });
        document.getElementById('btn-back-target').addEventListener('click', () => {
            showStep('target');
        });
        document.getElementById('btn-analyze').addEventListener('click', () => {
            vscode.postMessage({ type: 'analyzeSelected' });
        });
        document.getElementById('btn-back-candidates').addEventListener('click', () => {
            showStep('candidates');
        });
        document.getElementById('btn-generate').addEventListener('click', () => {
            vscode.postMessage({ type: 'generateTests' });
        });
        document.getElementById('btn-back-analysis').addEventListener('click', () => {
            showStep('analysis');
        });
        document.getElementById('btn-apply-all').addEventListener('click', () => {
            vscode.postMessage({ type: 'applyAllSelected' });
        });

        // Show/hide steps
        function showStep(step) {
            stepTarget.classList.add('hidden');
            stepCandidates.classList.add('hidden');
            stepAnalysis.classList.add('hidden');
            stepPreview.classList.add('hidden');
            loading.classList.add('hidden');

            switch (step) {
                case 'target': stepTarget.classList.remove('hidden'); break;
                case 'candidates': stepCandidates.classList.remove('hidden'); break;
                case 'analysis': stepAnalysis.classList.remove('hidden'); break;
                case 'preview': stepPreview.classList.remove('hidden'); break;
                case 'loading': loading.classList.remove('hidden'); break;
            }
        }

        function showLoading(text) {
            loadingText.textContent = text;
            document.getElementById('loading-timeout').classList.add('hidden');
            // Clear any previous timeout
            if (loadingTimeoutId) {
                clearTimeout(loadingTimeoutId);
            }
            // Show warning after 30 seconds
            loadingTimeoutId = setTimeout(() => {
                document.getElementById('loading-timeout').classList.remove('hidden');
            }, 30000);
            showStep('loading');
        }

        function hideLoading() {
            if (loadingTimeoutId) {
                clearTimeout(loadingTimeoutId);
                loadingTimeoutId = null;
            }
            document.getElementById('loading-timeout').classList.add('hidden');
        }

        // Message handler
        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.type) {
                case 'pathSelected':
                    targetPath = message.path;
                    targetInput.value = targetPath;
                    document.getElementById('btn-scan').disabled = false;
                    break;

                case 'scanning':
                    showLoading('Scanning for test candidates...');
                    break;

                case 'candidates':
                    hideLoading();
                    candidates = message.candidates;
                    selectedFiles = new Set(candidates.filter(c => c.priority >= 50 || c.is_hotspot).map(c => c.file));
                    document.getElementById('stat-total').textContent = message.summary.total;
                    document.getElementById('stat-hotspots').textContent = message.summary.hotspots;
                    document.getElementById('stat-untested').textContent = message.summary.untested;
                    renderCandidates();
                    showStep('candidates');
                    break;

                case 'analyzing':
                    showLoading('Analyzing code structure...');
                    break;

                case 'analysis':
                    hideLoading();
                    analysis = message.analysis;
                    selectedTargets = {};
                    analysis.forEach(a => {
                        selectedTargets[a.file] = new Set([
                            ...a.functions.map(f => f.name),
                            ...a.classes.map(c => c.name)
                        ]);
                    });
                    document.getElementById('stat-functions').textContent = message.totals.functions;
                    document.getElementById('stat-classes').textContent = message.totals.classes;
                    renderAnalysis();
                    showStep('analysis');
                    break;

                case 'generating':
                    showLoading('Generating tests...');
                    break;

                case 'generated':
                    hideLoading();
                    generatedTests = message.tests;
                    document.getElementById('stat-tests').textContent = message.totalTests;
                    renderPreview();
                    showStep('preview');
                    break;

                case 'testApplied':
                    // Update the Apply button for this specific test
                    if (message.success) {
                        // Find and update the button that was clicked
                        const buttons = document.querySelectorAll('.preview-test button');
                        buttons.forEach((btn, idx) => {
                            // Match by checking sourceFile and testIndex from the onclick
                            const onclickAttr = btn.getAttribute('onclick') || '';
                            if (onclickAttr.includes(message.sourceFile) && onclickAttr.includes(message.testIndex.toString())) {
                                btn.textContent = '✓ Applied';
                                btn.disabled = true;
                                btn.classList.add('button-success');
                            }
                        });
                    }
                    break;

                case 'allTestsApplied':
                    // Show completion state
                    const resultMsg = message.applied > 0
                        ? 'Successfully applied ' + message.applied + ' test file(s)!' + (message.failed > 0 ? ' (' + message.failed + ' failed)' : '')
                        : message.failed > 0 ? 'Failed to apply ' + message.failed + ' test file(s)' : 'No tests to apply';
                    alert(resultMsg);
                    // Update button to show completed state
                    const applyBtn = document.getElementById('btn-apply-all');
                    if (applyBtn && message.applied > 0) {
                        applyBtn.textContent = '✓ Applied ' + message.applied + ' Files';
                        applyBtn.disabled = true;
                    }
                    break;

                case 'operationCancelled':
                    hideLoading();
                    showStep('target');
                    break;

                case 'error':
                    hideLoading();
                    alert(message.message);
                    showStep('target');
                    break;

                case 'healthStatus':
                    updateHealthIndicator(message.health);
                    break;

                case 'activeFileChanged':
                    document.getElementById('active-file-name').textContent = message.fileName || 'None';
                    break;
            }
        });

        // Render functions
        function renderCandidates() {
            const list = document.getElementById('candidates-list');
            list.innerHTML = '';

            if (candidates.length === 0) {
                list.innerHTML = '<div class="empty-state">No files found that need tests</div>';
                return;
            }

            candidates.forEach(c => {
                const item = document.createElement('div');
                item.className = 'list-item' + (selectedFiles.has(c.file) ? ' selected' : '');
                item.innerHTML = \`
                    <input type="checkbox" \${selectedFiles.has(c.file) ? 'checked' : ''}>
                    <div class="list-item-content">
                        <div class="list-item-title">\${c.file}</div>
                        <div class="list-item-meta">
                            \${c.lines} lines
                            \${c.is_hotspot ? '<span class="badge badge-hotspot">hotspot</span>' : ''}
                            <span class="badge badge-priority">\${c.priority}</span>
                        </div>
                    </div>
                \`;

                const checkbox = item.querySelector('input');
                checkbox.addEventListener('change', (e) => {
                    if (e.target.checked) {
                        selectedFiles.add(c.file);
                        item.classList.add('selected');
                    } else {
                        selectedFiles.delete(c.file);
                        item.classList.remove('selected');
                    }
                    vscode.postMessage({ type: 'selectFile', file: c.file, selected: e.target.checked });
                });

                list.appendChild(item);
            });
        }

        function renderAnalysis() {
            const tree = document.getElementById('analysis-tree');
            tree.innerHTML = '';

            if (analysis.length === 0) {
                tree.innerHTML = '<div class="empty-state">No functions or classes found</div>';
                return;
            }

            analysis.forEach(a => {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'tree-file';

                const allTargets = [...a.functions.map(f => f.name), ...a.classes.map(c => c.name)];
                const allSelected = selectedTargets[a.file] && allTargets.every(t => selectedTargets[a.file].has(t));

                fileDiv.innerHTML = \`
                    <div class="tree-file-header">
                        <span class="tree-arrow expanded">▶</span>
                        <input type="checkbox" \${allSelected ? 'checked' : ''}>
                        <span style="flex:1">\${a.file}</span>
                        <span style="font-size:10px;color:var(--vscode-descriptionForeground)">
                            \${a.function_count}f / \${a.class_count}c
                        </span>
                    </div>
                    <div class="tree-items"></div>
                \`;

                const header = fileDiv.querySelector('.tree-file-header');
                const arrow = header.querySelector('.tree-arrow');
                const items = fileDiv.querySelector('.tree-items');
                const fileCheckbox = header.querySelector('input');

                // Toggle expand/collapse
                arrow.addEventListener('click', (e) => {
                    e.stopPropagation();
                    arrow.classList.toggle('expanded');
                    items.classList.toggle('hidden');
                });

                // Select all in file
                fileCheckbox.addEventListener('change', (e) => {
                    const checked = e.target.checked;
                    items.querySelectorAll('input').forEach(cb => cb.checked = checked);
                    if (checked) {
                        selectedTargets[a.file] = new Set(allTargets);
                    } else {
                        selectedTargets[a.file] = new Set();
                    }
                    vscode.postMessage({ type: 'selectAllInFile', file: a.file, selected: checked });
                });

                // Render functions
                a.functions.forEach(f => {
                    const item = document.createElement('div');
                    item.className = 'tree-item';
                    const isSelected = selectedTargets[a.file]?.has(f.name);
                    item.innerHTML = \`
                        <input type="checkbox" \${isSelected ? 'checked' : ''}>
                        <span class="tree-item-name">\${f.name}()</span>
                        \${f.is_async ? '<span class="badge badge-async">async</span>' : ''}
                        <span class="badge badge-complexity">C:\${f.complexity}</span>
                    \`;

                    const cb = item.querySelector('input');
                    cb.addEventListener('change', (e) => {
                        if (!selectedTargets[a.file]) selectedTargets[a.file] = new Set();
                        if (e.target.checked) {
                            selectedTargets[a.file].add(f.name);
                        } else {
                            selectedTargets[a.file].delete(f.name);
                        }
                        vscode.postMessage({ type: 'selectTarget', file: a.file, target: f.name, selected: e.target.checked });
                    });

                    items.appendChild(item);
                });

                // Render classes
                a.classes.forEach(c => {
                    const item = document.createElement('div');
                    item.className = 'tree-item';
                    const isSelected = selectedTargets[a.file]?.has(c.name);
                    item.innerHTML = \`
                        <input type="checkbox" \${isSelected ? 'checked' : ''}>
                        <span class="tree-item-name">class \${c.name}</span>
                        <span class="badge">\${c.methods.length} methods</span>
                    \`;

                    const cb = item.querySelector('input');
                    cb.addEventListener('change', (e) => {
                        if (!selectedTargets[a.file]) selectedTargets[a.file] = new Set();
                        if (e.target.checked) {
                            selectedTargets[a.file].add(c.name);
                        } else {
                            selectedTargets[a.file].delete(c.name);
                        }
                        vscode.postMessage({ type: 'selectTarget', file: a.file, target: c.name, selected: e.target.checked });
                    });

                    items.appendChild(item);
                });

                tree.appendChild(fileDiv);
            });
        }

        function renderPreview() {
            const container = document.getElementById('test-preview');
            container.innerHTML = '';

            if (generatedTests.length === 0) {
                container.innerHTML = '<div class="empty-state">No tests generated</div>';
                return;
            }

            generatedTests.forEach(tf => {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'preview-file';

                fileDiv.innerHTML = \`
                    <div class="preview-file-header">
                        <span class="preview-file-name">\${tf.test_file}</span>
                        <span style="font-size:10px">\${tf.test_count} tests</span>
                    </div>
                \`;

                tf.tests.forEach((test, idx) => {
                    const testDiv = document.createElement('div');
                    testDiv.className = 'preview-test';
                    testDiv.innerHTML = \`
                        <div class="preview-test-header">
                            <span class="preview-test-name">\${test.target} (\${test.type})</span>
                            <button class="button button-secondary" style="padding:2px 8px;font-size:10px"
                                    onclick="applyTest('\${tf.source_file}', \${idx})">Apply</button>
                        </div>
                        <div class="preview-code">\${highlightCode(test.code)}</div>
                    \`;
                    fileDiv.appendChild(testDiv);
                });

                container.appendChild(fileDiv);
            });
        }

        function highlightCode(code) {
            if (!code) return '';

            let escaped = code
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');

            // Python keywords
            const kwPattern = /\\b(def|class|if|elif|else|for|while|return|import|from|as|try|except|finally|with|async|await|yield|lambda|pass|break|continue|raise|in|is|not|and|or|True|False|None|assert)\\b/g;

            escaped = escaped
                .replace(/(#[^\\n]*)/g, '<span class="comment">$1</span>')
                .replace(/(@\\w+)/g, '<span class="decorator">$1</span>')
                .replace(/('[^'\\n]*'|"[^"\\n]*")/g, '<span class="string">$1</span>')
                .replace(/\\b(\\d+\\.?\\d*)\\b/g, '<span class="number">$1</span>')
                .replace(kwPattern, '<span class="keyword">$1</span>')
                .replace(/\\b([a-zA-Z_]\\w*)(\\s*\\()/g, '<span class="function">$1</span>$2');

            return escaped;
        }

        function applyTest(sourceFile, testIndex) {
            vscode.postMessage({ type: 'applyTest', sourceFile, testIndex });
        }

        // Make applyTest available globally
        window.applyTest = applyTest;

        function updateHealthIndicator(health) {
            const indicator = document.getElementById('health-indicator');
            const text = document.getElementById('health-text');

            indicator.classList.remove('health-ok', 'health-degraded', 'health-unknown');

            if (health.status === 'ok') {
                indicator.classList.add('health-ok');
                text.textContent = 'Backend: OK';
            } else if (health.status === 'degraded') {
                indicator.classList.add('health-degraded');
                text.textContent = 'Backend: Degraded (' + health.consecutiveFailures + ' failures)';
            } else {
                indicator.classList.add('health-unknown');
                text.textContent = 'Backend: Unknown';
            }
        }

        // Request initial state
        vscode.postMessage({ type: 'getSessionState' });
    </script>
</body>
</html>`;
    }
}
