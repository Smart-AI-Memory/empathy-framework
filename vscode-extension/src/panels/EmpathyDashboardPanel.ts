/**
 * Empathy Dashboard Panel - Activity Bar Webview
 *
 * Replaces tree views with a rich webview dashboard featuring:
 * - Tabbed interface (Patterns, Health, Costs, Workflows)
 * - Interactive charts using Chart.js
 * - Real-time updates via file watchers
 * - One-click actions for common tasks
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as cp from 'child_process';
import { getFilePickerService, FilePickerService } from '../services/FilePickerService';

export class EmpathyDashboardProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'empathy-dashboard';

    private _view?: vscode.WebviewView;
    private _extensionUri: vscode.Uri;
    private _context: vscode.ExtensionContext;
    private _fileWatcher?: vscode.FileSystemWatcher;
    private _workflowHistory: Map<string, string> = new Map();
    private _filePickerService: FilePickerService;

    constructor(extensionUri: vscode.Uri, context: vscode.ExtensionContext) {
        this._extensionUri = extensionUri;
        this._context = context;
        this._filePickerService = getFilePickerService();
        // Load workflow history from globalState
        const saved = context.globalState.get<Record<string, string>>('workflowHistory', {});
        this._workflowHistory = new Map(Object.entries(saved));
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Handle messages from webview
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.type) {
                case 'runCommand':
                    try {
                        // Special handling for run-tests (runs pytest directly)
                        if (message.command === 'run-tests') {
                            await this._runTests();
                        } else if (message.command === 'initialize') {
                            // Launch the Initialize Wizard (force open, bypass "already initialized" check)
                            await vscode.commands.executeCommand('empathy.initializeProject', { force: true });
                        } else {
                            const cmdName = `empathy.${message.command}`;
                            // Check if command exists before executing
                            const allCommands = await vscode.commands.getCommands(true);
                            if (allCommands.includes(cmdName)) {
                                await vscode.commands.executeCommand(cmdName);
                            } else {
                                vscode.window.showWarningMessage(`Command not found: ${cmdName}`);
                            }
                        }
                    } catch (err) {
                        vscode.window.showErrorMessage(`Command failed: ${err}`);
                    }
                    break;
                case 'refresh':
                    await this._updateData();
                    break;
                case 'openFile':
                    await this._openFile(message.filePath, message.line);
                    break;
                case 'fixIssue':
                    await this._fixIssue(message.issueType);
                    break;
                case 'runWorkflow':
                    try {
                        await this._runWorkflow(message.workflow, message.input);
                    } catch (err) {
                        vscode.window.showErrorMessage(`Workflow failed: ${err}`);
                    }
                    break;
                case 'getCosts':
                    this._sendCostsData();
                    break;
                case 'getModelConfig':
                    this._sendModelConfigData();
                    break;
                case 'showFilePicker':
                    await this._showFilePicker(message.workflow);
                    break;
                case 'showFolderPicker':
                    await this._showFolderPicker(message.workflow);
                    break;
                case 'showDropdown':
                    await this._showDropdown(message.workflow, message.options);
                    break;
                case 'getActiveFile':
                    this._sendActiveFile(message.workflow);
                    break;
                case 'openWebDashboard':
                    vscode.commands.executeCommand('empathy.openWebDashboard');
                    break;
                case 'openHealthPanel':
                    vscode.commands.executeCommand('empathy.openHealthPanel');
                    break;
                case 'openCoveragePanel':
                    vscode.commands.executeCommand('empathy.openCoveragePanel');
                    break;
                case 'runOrchestratedHealthCheck':
                    await this._runOrchestratedHealthCheck();
                    break;
                case 'runOrchestratedReleasePrep':
                    await this._runOrchestratedReleasePrep();
                    break;
                case 'runOrchestratedTestCoverage':
                    await this._runOrchestratedTestCoverage();
                    break;
                case 'copyToClipboard':
                    await vscode.env.clipboard.writeText(message.content);
                    vscode.window.showInformationMessage('Report copied to clipboard');
                    break;
                case 'askClaude':
                    await this._askClaude(message.content);
                    break;
                case 'estimateCost':
                    await this._estimateCost(message.workflow, message.input);
                    break;
                case 'openWorkflowWizard':
                    // HIDDEN in v3.5.5: Workflow Wizard temporarily disabled
                    vscode.window.showInformationMessage('Workflow Wizard is temporarily disabled. Use "empathy wizard create" CLI instead.');
                    break;
                case 'openDocAnalysis':
                    vscode.commands.executeCommand('empathy.openDocAnalysis');
                    break;
                case 'openTestGenerator':
                    // Run test-gen workflow directly (panel removed in v3.5.5)
                    console.log('[EmpathyDashboard] Running test-gen workflow directly');
                    await this._runWorkflow('test-gen');
                    break;
                case 'runWorkflowInEditor':
                    console.log('[EmpathyDashboard] Received runWorkflowInEditor:', message.workflow);
                    await this._runWorkflowInEditor(message.workflow, message.input);
                    break;
                case 'openHealthPanel':
                    vscode.commands.executeCommand('empathy.openHealthPanel');
                    break;
                case 'openCostsPanel':
                    vscode.commands.executeCommand('empathy.openCostsPanel');
                    break;
                case 'openWorkflowHistory':
                    vscode.commands.executeCommand('empathy.openWorkflowHistory');
                    break;
                case 'runAgentTeam':
                    await this._runAgentTeam(message.skill, message.template, message.label);
                    break;
                case 'runSkill':
                    await this._runSkill(message.skill, message.label);
                    break;
                case 'createDynamic':
                    await this._createDynamic(message.createType);
                    break;
            }
        });

        // Set up file watcher for data files
        this._setupFileWatcher();

        // Initial data load
        this._updateData();
    }

    private _setupFileWatcher() {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            return;
        }

        // Watch for changes to empathy data files
        this._fileWatcher = vscode.workspace.createFileSystemWatcher(
            new vscode.RelativePattern(workspaceFolder, '**/.empathy/*.json')
        );

        const debouncedUpdate = this._debounce(() => this._updateData(), 1000);

        this._fileWatcher.onDidChange(debouncedUpdate);
        this._fileWatcher.onDidCreate(debouncedUpdate);
        this._fileWatcher.onDidDelete(debouncedUpdate);
    }

    private _debounce(fn: () => void, delay: number) {
        let timeout: NodeJS.Timeout;
        return () => {
            clearTimeout(timeout);
            timeout = setTimeout(fn, delay);
        };
    }

    public refresh() {
        this._updateData();
    }

    private async _updateData() {
        if (!this._view) {
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            return;
        }

        const config = vscode.workspace.getConfiguration('empathy');
        const patternsDir = path.join(workspaceFolder, config.get<string>('patternsDir', './patterns'));
        const empathyDir = path.join(workspaceFolder, config.get<string>('empathyDir', '.empathy'));

        const errors: Record<string, string> = {};

        // Load patterns with error handling
        let patterns: PatternData[] = [];
        try {
            patterns = this._loadPatterns(patternsDir);
        } catch (e) {
            errors.patterns = `Failed to load patterns: ${e}`;
        }

        // Load health with error handling
        let health: HealthData | null = null;
        try {
            health = this._loadHealth(empathyDir, patternsDir);
        } catch (e) {
            errors.health = `Failed to load health: ${e}`;
        }

        // Fetch costs with error handling
        let costs = this._getEmptyCostData();
        try {
            costs = await this._fetchCostsFromCLI();
        } catch (e) {
            errors.costs = `Failed to load costs: ${e}`;
        }

        // Load workflows with error handling
        let workflows: WorkflowData = {
            totalRuns: 0,
            successfulRuns: 0,
            totalCost: 0,
            totalSavings: 0,
            recentRuns: [],
            byWorkflow: {}
        };
        try {
            workflows = this._loadWorkflows(empathyDir);
        } catch (e) {
            errors.workflows = `Failed to load workflows: ${e}`;
        }

        const data = {
            patterns,
            patternsEmpty: patterns.length === 0,
            health,
            healthEmpty: !health || health.score === undefined,
            costs,
            costsEmpty: costs.totalCost === 0 && costs.requests === 0,
            workflows,
            workflowsEmpty: workflows.totalRuns === 0,
            errors,
            hasErrors: Object.keys(errors).length > 0,
            workflowLastInputs: Object.fromEntries(this._workflowHistory),
        };

        this._view.webview.postMessage({ type: 'update', data });
    }

    private _loadPatterns(patternsDir: string): PatternData[] {
        const patterns: PatternData[] = [];

        try {
            const debuggingFile = path.join(patternsDir, 'debugging.json');
            if (fs.existsSync(debuggingFile)) {
                const data = JSON.parse(fs.readFileSync(debuggingFile, 'utf8'));
                for (const p of (data.patterns || []).slice(-20)) {
                    patterns.push({
                        id: p.pattern_id || 'unknown',
                        type: p.bug_type || 'unknown',
                        status: p.status || 'investigating',
                        rootCause: p.root_cause || '',
                        fix: p.fix || '',
                        files: p.files_affected || [],
                        timestamp: p.timestamp || '',
                    });
                }
            }
        } catch { /* ignore */ }

        return patterns.reverse();
    }

    private _loadHealth(empathyDir: string, patternsDir: string): HealthData {
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

        try {
            const debuggingFile = path.join(patternsDir, 'debugging.json');
            if (fs.existsSync(debuggingFile)) {
                const data = JSON.parse(fs.readFileSync(debuggingFile, 'utf8'));
                health.patterns = data.patterns?.length || 0;
            }
        } catch { /* ignore */ }

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
                health.lastUpdated = data.timestamp || null;
            }
        } catch { /* ignore */ }

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
        if (health.score === 0 && health.patterns > 0) {
            let score = 100;
            score -= health.lint.errors * 2;
            score -= health.types.errors * 3;
            score -= health.security.high * 10;
            score -= health.tests.failed * 5;
            health.score = Math.max(0, Math.min(100, Math.round(score)));
        }

        return health;
    }

    private _getEmptyCostData(): CostData {
        return {
            totalCost: 0,
            totalSavings: 0,
            savingsPercent: 0,
            requests: 0,
            baselineCost: 0,
            dailyCosts: [],
            byProvider: {},
            byTier: undefined,
        };
    }

    /**
     * Fetch costs from telemetry CLI (preferred method).
     * Falls back to file-based loading if CLI fails.
     */
    private async _fetchCostsFromCLI(): Promise<CostData> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            return this._getEmptyCostData();
        }

        const config = vscode.workspace.getConfiguration('empathy');
        const pythonPath = config.get<string>('pythonPath', 'python');
        const empathyDir = path.join(workspaceFolder, config.get<string>('empathyDir', '.empathy'));

        return new Promise((resolve) => {
            const proc = cp.spawn(pythonPath, [
                '-m', 'empathy_os.models.cli', 'telemetry', '--costs', '-f', 'json', '-d', '30'
            ], { cwd: workspaceFolder });

            let stdout = '';
            let stderr = '';
            proc.stdout.on('data', (data: Buffer) => { stdout += data.toString(); });
            proc.stderr.on('data', (data: Buffer) => { stderr += data.toString(); });

            proc.on('close', (code) => {
                if (code === 0 && stdout) {
                    try {
                        const data: TelemetryCostData = JSON.parse(stdout.trim());
                        resolve({
                            totalCost: data.total_actual_cost || 0,
                            totalSavings: data.total_savings || 0,
                            savingsPercent: data.savings_percent || 0,
                            requests: data.workflow_count || 0,
                            baselineCost: data.total_baseline_cost || 0,
                            dailyCosts: [],
                            byProvider: {},
                        });
                    } catch {
                        // JSON parse failed, fall back to file
                        resolve(this._loadCostsFromFile(empathyDir));
                    }
                } else {
                    // CLI failed, fall back to file-based loading
                    resolve(this._loadCostsFromFile(empathyDir));
                }
            });

            // Timeout after 5 seconds
            setTimeout(() => {
                proc.kill();
                resolve(this._loadCostsFromFile(empathyDir));
            }, 5000);
        });
    }

    /**
     * Load costs from .empathy/costs.json file (fallback method).
     */
    private _loadCostsFromFile(empathyDir: string): CostData {
        const costs: CostData = this._getEmptyCostData();

        try {
            const costsFile = path.join(empathyDir, 'costs.json');
            if (fs.existsSync(costsFile)) {
                const data = JSON.parse(fs.readFileSync(costsFile, 'utf8'));
                let baselineCost = 0;

                for (const [dateStr, daily] of Object.entries(data.daily_totals || {})) {
                    const d = daily as any;
                    costs.totalCost += d.actual_cost || 0;
                    costs.totalSavings += d.savings || 0;
                    costs.requests += d.requests || 0;
                    baselineCost += d.baseline_cost || 0;

                    costs.dailyCosts.push({
                        date: dateStr,
                        cost: d.actual_cost || 0,
                        savings: d.savings || 0,
                    });
                }

                costs.baselineCost = baselineCost;
                costs.savingsPercent = baselineCost > 0 ? Math.round((costs.totalSavings / baselineCost) * 100) : 0;

                // By provider
                for (const [provider, providerData] of Object.entries(data.by_provider || {})) {
                    costs.byProvider[provider] = {
                        requests: (providerData as any).requests || 0,
                        cost: (providerData as any).actual_cost || 0,
                    };
                }

                // Sort daily costs by date
                costs.dailyCosts.sort((a, b) => a.date.localeCompare(b.date));
            }
        } catch { /* ignore */ }

        return costs;
    }

    private _sendCostsData() {
        if (!this._view) {
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            this._view.webview.postMessage({
                type: 'costsData',
                data: { requests: [], totalSavings: 0, totalCost: 0, savingsPercent: 0 }
            });
            return;
        }

        const config = vscode.workspace.getConfiguration('empathy');
        const empathyDir = path.join(workspaceFolder, config.get<string>('empathyDir', '.empathy'));

        try {
            const costsFile = path.join(empathyDir, 'costs.json');
            if (!fs.existsSync(costsFile)) {
                this._view.webview.postMessage({
                    type: 'costsData',
                    data: { requests: [], totalSavings: 0, totalCost: 0, savingsPercent: 0 }
                });
                return;
            }

            const data = JSON.parse(fs.readFileSync(costsFile, 'utf8'));

            // Get last 10 requests
            const requests = (data.requests || []).slice(-10).reverse();

            // Calculate 7-day totals and build daily costs array
            let totalSavings = 0;
            let totalCost = 0;
            let baselineCost = 0;
            const byTier: Record<string, { requests: number; savings: number; cost: number }> = {};
            const dailyCosts: Array<{ date: string; cost: number; savings: number }> = [];
            const byProvider: Record<string, { requests: number; cost: number }> = {};

            const cutoff = new Date();
            cutoff.setDate(cutoff.getDate() - 7);
            const cutoffStr = cutoff.toISOString().split('T')[0];

            for (const [dateStr, daily] of Object.entries(data.daily_totals || {})) {
                if (dateStr >= cutoffStr) {
                    const d = daily as any;
                    totalCost += d.actual_cost || 0;
                    totalSavings += d.savings || 0;
                    baselineCost += d.baseline_cost || 0;
                    dailyCosts.push({
                        date: dateStr,
                        cost: d.actual_cost || 0,
                        savings: d.savings || 0
                    });
                }
            }

            // Sort daily costs by date
            dailyCosts.sort((a, b) => a.date.localeCompare(b.date));

            const savingsPercent = baselineCost > 0 ? Math.round((totalSavings / baselineCost) * 100) : 0;

            // 7-day tier breakdown and provider breakdown based on per-request data
            const cutoffIso = cutoff.toISOString();
            for (const req of requests as any[]) {
                if (!req || typeof req.timestamp !== 'string') {
                    continue;
                }
                if (req.timestamp < cutoffIso) {
                    // Only count requests in the same 7-day window
                    continue;
                }

                // Tier breakdown
                const tier = (req.tier as string) || 'capable';
                if (!byTier[tier]) {
                    byTier[tier] = { requests: 0, savings: 0, cost: 0 };
                }
                byTier[tier].requests += 1;
                byTier[tier].savings += req.savings || 0;
                byTier[tier].cost += req.actual_cost || 0;

                // Provider breakdown
                const provider = (req.provider as string) || 'unknown';
                if (!byProvider[provider]) {
                    byProvider[provider] = { requests: 0, cost: 0 };
                }
                byProvider[provider].requests += 1;
                byProvider[provider].cost += req.actual_cost || 0;
            }

            // Also check for by_provider in the data file
            if (data.by_provider) {
                for (const [provider, pdata] of Object.entries(data.by_provider || {})) {
                    const pd = pdata as any;
                    if (!byProvider[provider]) {
                        byProvider[provider] = { requests: 0, cost: 0 };
                    }
                    // Use file data if request-based data is empty
                    if (byProvider[provider].requests === 0) {
                        byProvider[provider].requests = pd.requests || 0;
                        byProvider[provider].cost = pd.actual_cost || 0;
                    }
                }
            }

            this._view.webview.postMessage({
                type: 'costsData',
                data: {
                    requests,
                    totalSavings,
                    totalCost,
                    savingsPercent,
                    byTier,
                    dailyCosts,
                    byProvider
                }
            });
        } catch {
            this._view.webview.postMessage({
                type: 'costsData',
                data: { requests: [], totalSavings: 0, totalCost: 0, savingsPercent: 0 }
            });
        }
    }

    private _sendModelConfigData() {
        if (!this._view) {
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

        // Default model configuration (using current model names)
        let modelConfig = {
            provider: 'anthropic',
            mode: 'single',
            models: {
                cheap: 'claude-3-5-haiku',
                capable: 'claude-sonnet-4-5',
                premium: 'claude-opus-4-5'
            }
        };

        if (workspaceFolder) {
            // Try to read from .env file
            const envFile = path.join(workspaceFolder, '.env');
            if (fs.existsSync(envFile)) {
                try {
                    const envContent = fs.readFileSync(envFile, 'utf8');

                    // Check for provider keys
                    const hasAnthropic = envContent.includes('ANTHROPIC_API_KEY');
                    const hasOpenAI = envContent.includes('OPENAI_API_KEY');

                    if (hasAnthropic && hasOpenAI) {
                        modelConfig.provider = 'Hybrid';
                        modelConfig.mode = 'hybrid';
                        modelConfig.models = {
                            cheap: 'gpt-4o-mini',
                            capable: 'claude-sonnet-4-5',
                            premium: 'claude-opus-4-5'
                        };
                    } else if (hasOpenAI && !hasAnthropic) {
                        modelConfig.provider = 'OpenAI';
                        modelConfig.mode = 'single';
                        modelConfig.models = {
                            cheap: 'gpt-4o-mini',
                            capable: 'gpt-4o',
                            premium: 'o1'
                        };
                    } else {
                        modelConfig.provider = 'Anthropic';
                    }
                } catch {
                    // Use defaults
                }
            }

            // Try to read from empathy config
            const config = vscode.workspace.getConfiguration('empathy');
            const empathyDir = path.join(workspaceFolder, config.get<string>('empathyDir', '.empathy'));
            const configFile = path.join(empathyDir, 'config.json');

            if (fs.existsSync(configFile)) {
                try {
                    const savedConfig = JSON.parse(fs.readFileSync(configFile, 'utf8'));
                    if (savedConfig.provider) {
                        modelConfig.provider = savedConfig.provider;
                    }
                    if (savedConfig.mode) {
                        modelConfig.mode = savedConfig.mode;
                    }
                    if (savedConfig.models) {
                        modelConfig.models = { ...modelConfig.models, ...savedConfig.models };
                    }
                } catch {
                    // Use defaults
                }
            }
        }

        this._view.webview.postMessage({
            type: 'modelConfig',
            data: modelConfig
        });
    }

    private _loadWorkflows(empathyDir: string): WorkflowData {
        const workflows: WorkflowData = {
            totalRuns: 0,
            successfulRuns: 0,
            totalCost: 0,
            totalSavings: 0,
            recentRuns: [],
            byWorkflow: {},
        };

        try {
            const runsFile = path.join(empathyDir, 'workflow_runs.json');
            if (fs.existsSync(runsFile)) {
                const runs = JSON.parse(fs.readFileSync(runsFile, 'utf8')) as any[];

                workflows.totalRuns = runs.length;
                workflows.successfulRuns = runs.filter(r => r.success).length;

                for (const run of runs) {
                    workflows.totalCost += run.cost || 0;
                    workflows.totalSavings += run.savings || 0;

                    const wfName = run.workflow || 'unknown';
                    if (!workflows.byWorkflow[wfName]) {
                        workflows.byWorkflow[wfName] = { runs: 0, cost: 0, savings: 0 };
                    }
                    workflows.byWorkflow[wfName].runs++;
                    workflows.byWorkflow[wfName].cost += run.cost || 0;
                    workflows.byWorkflow[wfName].savings += run.savings || 0;
                }

                workflows.recentRuns = runs.slice(-10).reverse().map(r => {
                    const run: WorkflowRunData = {
                        workflow: r.workflow || 'unknown',
                        success: r.success || false,
                        cost: r.cost || 0,
                        savings: r.savings || 0,
                        timestamp: r.started_at || '',
                    };
                    // Include XML-parsed fields if available
                    if (r.xml_parsed) {
                        run.xml_parsed = true;
                        run.summary = r.summary;
                        run.findings = r.findings || [];
                        run.checklist = r.checklist || [];
                    }
                    return run;
                });
            }
        } catch { /* ignore */ }

        return workflows;
    }

    private async _openFile(filePath: string, line?: number) {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder || !filePath) {
            return;
        }

        const fullPath = path.isAbsolute(filePath) ? filePath : path.join(workspaceFolder, filePath);

        try {
            const doc = await vscode.workspace.openTextDocument(fullPath);
            const editor = await vscode.window.showTextDocument(doc);
            if (line && line > 0) {
                const position = new vscode.Position(line - 1, 0);
                editor.selection = new vscode.Selection(position, position);
                editor.revealRange(new vscode.Range(position, position));
            }
        } catch {
            vscode.window.showErrorMessage(`Could not open file: ${filePath}`);
        }
    }

    private async _fixIssue(issueType: string) {
        const commandMap: Record<string, string> = {
            'lint': 'empathy.fixLint',
            'format': 'empathy.fixFormat',
            'tests': 'empathy.runTests',
            'security': 'empathy.runScan',
            'all': 'empathy.fixAll'
        };

        const cmd = commandMap[issueType];
        if (cmd) {
            await vscode.commands.executeCommand(cmd);
            // Auto-refresh dashboard data after fix completes
            // Add a short delay to let the fix command finish writing files
            setTimeout(() => this._updateData(), 1000);
        }
    }

    /**
     * Save workflow input to history for persistence.
     */
    private async _saveWorkflowInput(workflowId: string, input: string): Promise<void> {
        this._workflowHistory.set(workflowId, input);
        await this._context.globalState.update(
            'workflowHistory',
            Object.fromEntries(this._workflowHistory)
        );
    }

    /**
     * Get last input for a workflow.
     */
    private _getLastWorkflowInput(workflowId: string): string | undefined {
        return this._workflowHistory.get(workflowId);
    }

    private async _runTests() {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }

        // Create terminal for test output
        const terminal = vscode.window.createTerminal({
            name: 'Empathy Tests',
            cwd: workspaceFolder
        });
        terminal.show();
        terminal.sendText('python -m pytest tests/ --no-cov -v');
    }

    private async _runOrchestratedHealthCheck() {
        // v4.6.7: Open Claude Code with command prefilled - user presses Enter to execute
        await this._openClaudeCodeWithCommand('/security-scan');
    }

    private async _runOrchestratedReleasePrep() {
        // v4.6.7: Open Claude Code with command prefilled - user presses Enter to execute
        await this._openClaudeCodeWithCommand('/release-prep');
    }

    private async _runOrchestratedTestCoverage() {
        // v4.6.7: Open Claude Code with command prefilled - user presses Enter to execute
        await this._openClaudeCodeWithCommand('/test-coverage');
    }

    private async _openClaudeCodeWithCommand(command: string) {
        // v4.6.7: Open Claude Code with command prefilled - user presses Enter to execute
        // This approach works for ALL skills including interactive ones that use AskUserQuestion
        try {
            // Open Claude Code sidebar
            await vscode.commands.executeCommand('claude-vscode.sidebar.open');

            // Small delay to ensure the panel is ready
            await new Promise(resolve => setTimeout(resolve, 200));

            // Focus the input
            await vscode.commands.executeCommand('claude-vscode.focus');

            // Small delay to ensure focus is set
            await new Promise(resolve => setTimeout(resolve, 100));

            // Try to type the command using VS Code's type command
            // This inserts text at the current cursor position
            await vscode.commands.executeCommand('type', { text: command });

            // Show helpful notification
            vscode.window.showInformationMessage(`Command "${command}" ready - press Enter to execute`);
        } catch (error) {
            // Fallback: copy to clipboard if typing doesn't work
            await vscode.env.clipboard.writeText(command);
            vscode.window.showInformationMessage(
                `Command copied to clipboard. Paste in Claude Code chat and press Enter.`,
                'Open Claude Code'
            ).then(selection => {
                if (selection === 'Open Claude Code') {
                    vscode.commands.executeCommand('claude-vscode.sidebar.open');
                }
            });
        }
    }

    private async _runAgentTeam(skill: string, _template: string, _label: string) {
        // v4.6.7: Open Claude Code with command prefilled - user presses Enter to execute
        await this._openClaudeCodeWithCommand(skill);
    }

    private async _runSkill(skill: string, _label: string) {
        // v4.6.7: Open Claude Code with command prefilled - user presses Enter to execute
        // This works for ALL skills including interactive ones that use AskUserQuestion
        await this._openClaudeCodeWithCommand(skill);
    }

    private async _createDynamic(createType: string) {
        // v4.6.7: Open Claude Code with command prefilled - user presses Enter to execute
        const skill = createType === 'agent' ? '/create-agent' : '/create-team';
        await this._openClaudeCodeWithCommand(skill);
    }

    private async _runWorkflow(workflowName: string, input?: string) {
        // Special handling for doc-orchestrator: open the Documentation Analysis panel
        if (workflowName === 'doc-orchestrator') {
            vscode.commands.executeCommand('empathy.openDocAnalysis');
            return;
        }

        // v4.6.7: All workflow buttons now open Claude Code with command prefilled
        // User presses Enter to execute - works for ALL skills including interactive ones
        const workflowToSkill: Record<string, string> = {
            'dependency-check': '/deps',
            'code-review': '/review',
            'bug-predict': '/debug',
            'perf-audit': '/profile',
            'refactor-plan': '/refactor',
            'security-audit': '/security-scan',
            'pr-review': '/review-pr',
        };

        const skill = workflowToSkill[workflowName];
        if (skill) {
            await this._openClaudeCodeWithCommand(skill);
            return;
        }

        // v4.0.0: Orchestrated workflows are handled by direct message handlers now
        // (No special routing needed - buttons send specific message types)

        // v3.5.5: test-gen now runs workflow directly (panel removed)

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }

        // Save input to history for persistence
        if (input) {
            await this._saveWorkflowInput(workflowName, input);
        }

        // Send "running" state to webview
        this._view?.webview.postMessage({
            type: 'workflowStatus',
            data: { workflow: workflowName, status: 'running', output: '' }
        });

        // Execute workflow and capture output - pass input as JSON with workflow-specific key
        const inputKeys: Record<string, string> = {
            'code-review': 'target',
            'doc-orchestrator': 'path',
            'bug-predict': 'target',
            'security-audit': 'target',
            'perf-audit': 'target',
            'test-gen': 'target',
            'refactor-plan': 'target',
            'dependency-check': 'scope',
            'health-check': 'path',
            'pro-review': 'diff',
            'pr-review': 'target_path'
        };
        const inputKey = inputKeys[workflowName] || 'query';

        // v4.6.3: Build arguments for 'empathy' CLI (not python -m)
        const args = ['workflow', 'run', workflowName];
        if (input) {
            const inputJson = JSON.stringify({ [inputKey]: input });
            args.push('--input', inputJson);
        }

        // Add --json flag for security-audit to get structured output
        if (workflowName === 'security-audit') {
            args.push('--json');
        }

        // Workflows that use file/folder pickers for scope should open reports in editor
        // These are the workflows where users select a target file/folder to analyze
        const filePickerWorkflows = [
            'code-review',      // file picker - select file to review
            'bug-predict',      // folder picker - select folder to analyze
            'security-audit',   // folder picker - select folder to audit
            'perf-audit',       // folder picker - select folder to profile
            'refactor-plan',    // folder picker - select folder to plan refactoring
            'pr-review',        // folder picker - select folder with PR changes
            'pro-review',       // hybrid - file/text for code review
            // NOTE: health-check, release-prep, test-coverage-boost run on whole project and show output in dashboard
        ];
        const opensInEditor = filePickerWorkflows.includes(workflowName);
        console.log(`[EmpathyDashboard] Workflow: ${workflowName}, opensInEditor: ${opensInEditor}`);

        // v4.6.3: Use 'empathy' CLI command directly (installed via pip)
        const empathyCmd = 'empathy';

        // Use execFile with array arguments to prevent command injection
        cp.execFile(empathyCmd, args, { cwd: workspaceFolder, maxBuffer: 1024 * 1024 * 5 }, async (error, stdout, stderr) => {
            const output = stdout || stderr || (error ? error.message : 'No output');
            const success = !error;

            // Special handling for security-audit: save findings and update diagnostics
            if (workflowName === 'security-audit' && stdout) {
                this._saveSecurityFindings(workspaceFolder, stdout);
            }

            // For report workflows, open output in editor instead of panel
            let openedInEditor = false;

            if (success && opensInEditor && output.trim()) {
                try {
                    await vscode.commands.executeCommand('empathy.openReportInEditor', {
                        workflowName,
                        output,
                        input
                    });
                    openedInEditor = true;
                    vscode.window.showInformationMessage(`${workflowName} report opened in editor`);
                } catch (openErr) {
                    vscode.window.showErrorMessage(`Failed to open report: ${openErr}`);
                }
            }

            this._view?.webview.postMessage({
                type: 'workflowStatus',
                data: {
                    workflow: workflowName,
                    status: success ? 'complete' : 'error',
                    output: openedInEditor ? '(Report opened in editor)' : output,
                    error: error ? error.message : null,
                    openedInEditor: openedInEditor
                }
            });
        });
    }

    /**
     * Run a workflow and open the result directly in the editor.
     * Called when user clicks a report workflow button in the Power tab.
     * Shows a file/folder picker first, then runs the workflow.
     */
    private async _runWorkflowInEditor(workflowName: string, _defaultInput: string): Promise<void> {
        console.log('[EmpathyDashboard] _runWorkflowInEditor called:', workflowName);

        // v3.5.5: test-gen now runs workflow directly (panel removed)

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }

        // Determine if this workflow needs a file or folder picker
        const folderWorkflows = ['bug-predict', 'security-audit', 'perf-audit', 'refactor-plan', 'health-check', 'pr-review'];
        const fileWorkflows = ['code-review', 'pro-review'];

        let selectedPath: string | undefined;

        if (folderWorkflows.includes(workflowName)) {
            // Show folder picker with ignoreFocusOut to prevent focus issues from webview
            const result = await vscode.window.showQuickPick([
                { label: '$(folder) Entire Project', description: 'Analyze the whole project', path: '.' },
                { label: '$(folder-opened) Select Folder...', description: 'Choose a specific folder', path: '__browse__' }
            ], {
                placeHolder: `Select scope for ${workflowName}`,
                ignoreFocusOut: true
            });

            if (!result) {
                return; // User cancelled
            }

            if (result.path === '__browse__') {
                const folderUri = await vscode.window.showOpenDialog({
                    canSelectFiles: false,
                    canSelectFolders: true,
                    canSelectMany: false,
                    defaultUri: vscode.Uri.file(workspaceFolder),
                    title: `Select folder for ${workflowName}`
                });
                if (!folderUri || folderUri.length === 0) {
                    return; // User cancelled
                }
                selectedPath = folderUri[0].fsPath;
            } else {
                selectedPath = result.path;
            }
        } else if (fileWorkflows.includes(workflowName)) {
            // Show file picker with ignoreFocusOut to prevent focus issues from webview
            const result = await vscode.window.showQuickPick([
                { label: '$(file) Current File', description: 'Analyze the active editor file', path: '__active__' },
                { label: '$(folder) Entire Project', description: 'Analyze the whole project', path: '.' },
                { label: '$(file-add) Select File...', description: 'Choose a specific file', path: '__browse__' }
            ], {
                placeHolder: `Select scope for ${workflowName}`,
                ignoreFocusOut: true
            });

            if (!result) {
                return; // User cancelled
            }

            if (result.path === '__active__') {
                const activeEditor = vscode.window.activeTextEditor;
                if (activeEditor) {
                    selectedPath = activeEditor.document.uri.fsPath;
                } else {
                    vscode.window.showWarningMessage('No active file. Using project root.');
                    selectedPath = '.';
                }
            } else if (result.path === '__browse__') {
                const fileUri = await vscode.window.showOpenDialog({
                    canSelectFiles: true,
                    canSelectFolders: false,
                    canSelectMany: false,
                    defaultUri: vscode.Uri.file(workspaceFolder),
                    title: `Select file for ${workflowName}`
                });
                if (!fileUri || fileUri.length === 0) {
                    return; // User cancelled
                }
                selectedPath = fileUri[0].fsPath;
            } else {
                selectedPath = result.path;
            }
        } else {
            selectedPath = '.';
        }

        // Display names for workflows
        const workflowDisplayNames: Record<string, string> = {
            'code-review': 'Code Review',
            'bug-predict': 'Bug Prediction',
            'security-audit': 'Security Audit',
            'perf-audit': 'Performance Audit',
            'refactor-plan': 'Refactoring Plan',
            'health-check': 'Health Check',
            'pr-review': 'PR Review',
            'pro-review': 'Code Analysis',
        };
        const displayName = workflowDisplayNames[workflowName] || workflowName;

        // Create WebView panel with spinner for loading state
        const panel = vscode.window.createWebviewPanel(
            'empathyReport',
            `${displayName} Report`,
            vscode.ViewColumn.One,
            { enableScripts: true }
        );

        // Collapse sidebar to give more space to the report
        vscode.commands.executeCommand('workbench.action.closeSidebar');

        // Show loading spinner
        panel.webview.html = this._getLoadingHtml(displayName, selectedPath);

        // Store output for copy functionality
        let lastOutput = '';

        // Handle messages from WebView
        panel.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'copy':
                    await vscode.env.clipboard.writeText(lastOutput);
                    vscode.window.showInformationMessage('Report copied to clipboard');
                    break;
                case 'runAgain':
                    panel.webview.html = this._getLoadingHtml(displayName, selectedPath);
                    runWorkflow();
                    break;
            }
        });

        // Build arguments
        const inputKeys: Record<string, string> = {
            'code-review': 'target',
            'bug-predict': 'target',
            'security-audit': 'target',
            'perf-audit': 'target',
            'refactor-plan': 'target',
            'health-check': 'path',
            'pr-review': 'target_path',
            'pro-review': 'diff'
        };
        const inputKey = inputKeys[workflowName] || 'target';
        // v4.6.3: Use 'empathy' CLI command directly
        const args = ['workflow', 'run', workflowName];
        const inputJson = JSON.stringify({ [inputKey]: selectedPath });
        args.push('--input', inputJson);

        // Function to run the workflow
        const runWorkflow = () => {
            cp.execFile('empathy', args, { cwd: workspaceFolder, maxBuffer: 1024 * 1024 * 5 }, async (error, stdout, stderr) => {
                const output = stdout || stderr || (error ? error.message : 'No output');
                lastOutput = output;
                const timestamp = new Date().toLocaleString();
                panel.webview.html = this._getReportHtml(displayName, selectedPath, timestamp, output, error ? error.message : null);
            });
        };

        // Run workflow initially
        runWorkflow();
    }

    /**
     * Generate HTML for the loading spinner view.
     */
    private _getLoadingHtml(displayName: string, targetPath: string): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${displayName} Report</title>
    <style>
        body {
            font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
            background: var(--vscode-editor-background, #1e1e1e);
            color: var(--vscode-editor-foreground, #d4d4d4);
            margin: 0;
            padding: 40px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 80vh;
        }
        .container {
            text-align: center;
            max-width: 500px;
        }
        h1 {
            color: var(--vscode-foreground, #fff);
            margin-bottom: 8px;
            font-size: 24px;
        }
        .target {
            color: var(--vscode-descriptionForeground, #888);
            font-size: 14px;
            margin-bottom: 40px;
        }
        .spinner-container {
            margin: 40px 0;
        }
        .spinner {
            width: 60px;
            height: 60px;
            border: 4px solid var(--vscode-input-border, #3c3c3c);
            border-top-color: var(--vscode-button-background, #0e639c);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .status {
            margin-top: 24px;
            font-size: 16px;
            color: var(--vscode-foreground, #d4d4d4);
        }
        .dots {
            display: inline-block;
        }
        .dots::after {
            content: '';
            animation: dots 1.5s steps(4, end) infinite;
        }
        @keyframes dots {
            0% { content: ''; }
            25% { content: '.'; }
            50% { content: '..'; }
            75% { content: '...'; }
            100% { content: ''; }
        }
        .hint {
            margin-top: 20px;
            font-size: 12px;
            color: var(--vscode-descriptionForeground, #666);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>${displayName} Report</h1>
        <div class="target">Target: ${this._escapeHtml(targetPath)}</div>
        <div class="spinner-container">
            <div class="spinner"></div>
        </div>
        <div class="status">Generating report<span class="dots"></span></div>
        <div class="hint">This may take a moment depending on the size of the target.</div>
    </div>
</body>
</html>`;
    }

    /**
     * Generate HTML for the final report view.
     */
    private _getReportHtml(displayName: string, targetPath: string, timestamp: string, output: string, errorMessage: string | null): string {
        const isError = errorMessage !== null;
        const statusColor = isError ? 'var(--vscode-errorForeground, #f14c4c)' : 'var(--vscode-testing-iconPassed, #73c991)';
        const statusText = isError ? 'Error' : 'Complete';
        const statusIcon = isError ? '✗' : '✓';

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${displayName} Report</title>
    <style>
        body {
            font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
            background: var(--vscode-editor-background, #1e1e1e);
            color: var(--vscode-editor-foreground, #d4d4d4);
            margin: 0;
            padding: 24px;
            line-height: 1.6;
        }
        .header {
            border-bottom: 1px solid var(--vscode-input-border, #3c3c3c);
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
            color: var(--vscode-foreground, #fff);
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
            background: var(--vscode-button-secondaryBackground, #3c3c3c);
            color: var(--vscode-button-secondaryForeground, #fff);
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
            background: var(--vscode-button-secondaryHoverBackground, #505050);
        }
        .action-btn.primary {
            background: var(--vscode-button-background, #0e639c);
            color: var(--vscode-button-foreground, #fff);
        }
        .action-btn.primary:hover {
            background: var(--vscode-button-hoverBackground, #1177bb);
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            background: ${isError ? 'rgba(241, 76, 76, 0.15)' : 'rgba(115, 201, 145, 0.15)'};
            color: ${statusColor};
        }
        .meta {
            display: flex;
            gap: 24px;
            font-size: 13px;
            color: var(--vscode-descriptionForeground, #888);
        }
        .meta-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .content {
            white-space: pre-wrap;
            font-family: var(--vscode-editor-font-family, 'Consolas', 'Monaco', monospace);
            font-size: 13px;
            background: var(--vscode-textCodeBlock-background, #2d2d2d);
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
        }
        .error-box {
            background: rgba(241, 76, 76, 0.1);
            border: 1px solid var(--vscode-errorForeground, #f14c4c);
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .error-title {
            color: var(--vscode-errorForeground, #f14c4c);
            font-weight: 600;
            margin-bottom: 8px;
        }
        .footer {
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid var(--vscode-input-border, #3c3c3c);
            font-size: 12px;
            color: var(--vscode-descriptionForeground, #666);
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
            <div class="meta-item">📁 ${this._escapeHtml(targetPath)}</div>
            <div class="meta-item">🕐 ${timestamp}</div>
        </div>
    </div>
    ${isError ? `
    <div class="error-box">
        <div class="error-title">Error Details</div>
        <div>${this._escapeHtml(errorMessage)}</div>
    </div>
    ` : ''}
    <div class="content">${this._escapeHtml(output)}</div>
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

    /**
     * Escape HTML special characters to prevent XSS.
     */
    private _escapeHtml(text: string): string {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Open workflow report output in a new editor document.
     * Formats the output as markdown for better readability.
     * Only called for workflows that use file/folder pickers for scope.
     */
    private async _openReportInEditor(workflowName: string, output: string, input?: string): Promise<void> {
        // Display names for file picker workflows
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

        const displayName = workflowNames[workflowName] || workflowName;
        const timestamp = new Date().toLocaleString();

        // Format the report as markdown
        let content = `# ${displayName} Report\n\n`;
        content += `**Generated:** ${timestamp}\n`;
        if (input) {
            content += `**Target:** ${input}\n`;
        }
        content += `\n---\n\n`;

        // Try to parse as JSON for structured formatting, otherwise use raw output
        try {
            const parsed = JSON.parse(output);
            content += this._formatJsonReport(parsed);
        } catch {
            // Not JSON, use the raw output
            content += output;
        }

        content += `\n\n---\n*Generated by Empathy Framework*`;

        // Create and show the document in the main editor area
        console.log(`[EmpathyDashboard] Creating report document for ${workflowName}, content length: ${content.length}`);
        const doc = await vscode.workspace.openTextDocument({
            content,
            language: 'markdown',
        });
        console.log(`[EmpathyDashboard] Document created, showing in editor...`);
        // Force open in editor column 1 (main editor area), not preview
        await vscode.window.showTextDocument(doc, {
            viewColumn: vscode.ViewColumn.One,
            preview: false,
            preserveFocus: false
        });
        console.log(`[EmpathyDashboard] Document shown in editor`);
    }

    /**
     * Format a JSON report object as readable markdown.
     */
    private _formatJsonReport(data: any): string {
        let content = '';

        // Handle common report structures
        if (data.summary) {
            content += `## Summary\n\n${data.summary}\n\n`;
        }

        if (data.findings && Array.isArray(data.findings)) {
            content += `## Findings\n\n`;
            for (const finding of data.findings) {
                const severity = finding.severity || finding.level || 'info';
                const title = finding.title || finding.message || finding.description || 'Finding';
                content += `### ${severity.toUpperCase()}: ${title}\n\n`;
                if (finding.description && finding.description !== title) {
                    content += `${finding.description}\n\n`;
                }
                if (finding.file || finding.location) {
                    content += `**Location:** ${finding.file || finding.location}`;
                    if (finding.line) {
                        content += `:${finding.line}`;
                    }
                    content += `\n\n`;
                }
                if (finding.recommendation || finding.fix) {
                    content += `**Recommendation:** ${finding.recommendation || finding.fix}\n\n`;
                }
            }
        }

        if (data.recommendations && Array.isArray(data.recommendations)) {
            content += `## Recommendations\n\n`;
            for (const rec of data.recommendations) {
                if (typeof rec === 'string') {
                    content += `- ${rec}\n`;
                } else {
                    content += `- ${rec.title || rec.description || JSON.stringify(rec)}\n`;
                }
            }
            content += `\n`;
        }

        if (data.metrics) {
            content += `## Metrics\n\n`;
            content += `| Metric | Value |\n`;
            content += `|--------|-------|\n`;
            for (const [key, value] of Object.entries(data.metrics)) {
                content += `| ${key} | ${value} |\n`;
            }
            content += `\n`;
        }

        if (data.checklist && Array.isArray(data.checklist)) {
            content += `## Checklist\n\n`;
            for (const item of data.checklist) {
                const checked = item.passed || item.checked ? 'x' : ' ';
                const label = item.label || item.name || item.description || item;
                content += `- [${checked}] ${label}\n`;
            }
            content += `\n`;
        }

        // If nothing was formatted, dump the raw JSON
        if (!content) {
            content = '```json\n' + JSON.stringify(data, null, 2) + '\n```\n';
        }

        return content;
    }

    /**
     * Save security audit findings to file and trigger diagnostics refresh
     */
    private _saveSecurityFindings(workspaceFolder: string, output: string): void {
        try {
            // Try to parse as JSON
            const result = JSON.parse(output);
            const empathyDir = path.join(workspaceFolder, '.empathy');

            // Ensure .empathy directory exists
            if (!fs.existsSync(empathyDir)) {
                fs.mkdirSync(empathyDir, { recursive: true });
            }

            // Save findings to file
            const findingsPath = path.join(empathyDir, 'security_findings.json');
            fs.writeFileSync(findingsPath, JSON.stringify(result, null, 2));

            // The file watcher in extension.ts will automatically trigger updateSecurityDiagnostics()
            console.log('Security findings saved to:', findingsPath);
        } catch (parseErr) {
            // Not JSON output - might be text format, ignore
            console.log('Security output not JSON, skipping findings save');
        }
    }

    private async _showFilePicker(workflow: string) {
        const result = await this._filePickerService.showFilePicker({
            title: `Select file for ${workflow}`,
            openLabel: 'Select'
        });

        if (result && result[0]) {
            this._view?.webview.postMessage({
                type: 'pickerResult',
                data: { workflow, path: result[0].path, cancelled: false }
            });
        } else {
            this._view?.webview.postMessage({
                type: 'pickerResult',
                data: { workflow, path: '', cancelled: true }
            });
        }
    }

    private async _showFolderPicker(workflow: string) {
        const result = await this._filePickerService.showFolderPicker({
            title: `Select folder for ${workflow}`,
            openLabel: 'Select Folder'
        });

        if (result) {
            this._view?.webview.postMessage({
                type: 'pickerResult',
                data: { workflow, path: result.path, cancelled: false }
            });
        } else {
            this._view?.webview.postMessage({
                type: 'pickerResult',
                data: { workflow, path: '', cancelled: true }
            });
        }
    }

    private async _showDropdown(workflow: string, options: string[]) {
        const result = await vscode.window.showQuickPick(options, {
            placeHolder: `Select option for ${workflow}`,
            title: workflow
        });

        this._view?.webview.postMessage({
            type: 'pickerResult',
            data: { workflow, path: result || '', cancelled: !result }
        });
    }

    private async _askClaude(content: string) {
        // Copy report to clipboard
        await vscode.env.clipboard.writeText(content);
        vscode.window.showInformationMessage('Report copied! Paste into Claude Code input.');
    }

    /**
     * Estimate cost for a workflow before running it.
     * Uses the token_estimator module for accurate predictions.
     */
    private async _estimateCost(workflowName: string, input: string) {
        if (!this._view) {
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            this._view.webview.postMessage({
                type: 'costEstimate',
                data: { workflow: workflowName, error: 'No workspace folder' }
            });
            return;
        }

        const config = vscode.workspace.getConfiguration('empathy');
        const pythonPath = config.get<string>('pythonPath', 'python');

        // Build arguments for token_estimator
        // CLI uses positional workflow arg and -i for input
        const args = [
            '-m', 'empathy_os.models.token_estimator',
            workflowName,
            '-i', input || '.'
        ];

        try {
            const result = await new Promise<string>((resolve, reject) => {
                const proc = cp.execFile(pythonPath, args, {
                    cwd: workspaceFolder,
                    maxBuffer: 1024 * 1024,
                    timeout: 10000
                }, (error, stdout, stderr) => {
                    if (error) {
                        reject(new Error(stderr || error.message));
                    } else {
                        resolve(stdout);
                    }
                });
            });

            const estimate = JSON.parse(result.trim());
            this._view.webview.postMessage({
                type: 'costEstimate',
                data: {
                    workflow: workflowName,
                    estimate: estimate
                }
            });
        } catch (error) {
            // Send error but don't block - estimation is optional
            this._view.webview.postMessage({
                type: 'costEstimate',
                data: {
                    workflow: workflowName,
                    error: `Estimation unavailable: ${error}`
                }
            });
        }
    }

    private _sendActiveFile(workflow: string) {
        const result = this._filePickerService.getActiveFile();

        this._view?.webview.postMessage({
            type: 'activeFile',
            data: { workflow, path: result?.path || '' }
        });
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        const nonce = getNonce();
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        const projectName = workspaceFolder ? path.basename(workspaceFolder.uri.fsPath) : 'project';
        const projectPath = './' + projectName;
        // Cache-busting timestamp ensures webview reloads with new content
        const cacheBuster = Date.now();

        return `<!DOCTYPE html>
<!-- Cache: ${cacheBuster} - Version 4 -->
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <title>Empathy Dashboard</title>
    <style>
        :root {
            --bg: var(--vscode-sideBar-background);
            --fg: var(--vscode-sideBar-foreground);
            --border: var(--vscode-panel-border);
            --button-bg: var(--vscode-button-background);
            --button-fg: var(--vscode-button-foreground);
            --tab-active: var(--vscode-tab-activeBackground);
            --tab-inactive: var(--vscode-tab-inactiveBackground);
            --success: var(--vscode-testing-iconPassed);
            --error: var(--vscode-testing-iconFailed);
            --warning: var(--vscode-editorWarning-foreground);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: var(--vscode-font-family);
            font-size: 12px;
            color: var(--fg);
            background: var(--bg);
            height: 100vh;
            overflow: hidden;
        }

        /* Cards */
        .card {
            background: var(--vscode-input-background);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 10px;
            margin-bottom: 10px;
        }

        .card-title {
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        /* Health Score Circle */
        .score-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 16px;
        }

        .score-circle {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 8px;
        }

        .score-circle.good { background: rgba(16, 185, 129, 0.2); color: var(--success); }
        .score-circle.warning { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
        .score-circle.bad { background: rgba(239, 68, 68, 0.2); color: var(--error); }

        /* Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }

        .metric {
            background: var(--vscode-input-background);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 8px;
            text-align: center;
        }

        .metric-value {
            font-size: 16px;
            font-weight: 600;
        }

        .metric-value.success { color: var(--success); }
        .metric-value.warning { color: var(--warning); }
        .metric-value.error { color: var(--error); }

        .metric-label {
            font-size: 10px;
            opacity: 0.7;
            margin-top: 2px;
        }

        /* List Items */
        .list-item {
            display: flex;
            align-items: center;
            padding: 6px 0;
            border-bottom: 1px solid var(--border);
            gap: 8px;
        }

        .list-item:last-child { border-bottom: none; }

        .list-item-icon {
            width: 16px;
            text-align: center;
        }

        .list-item-content { flex: 1; min-width: 0; }
        .list-item-title { font-weight: 500; }
        .list-item-desc { font-size: 10px; opacity: 0.7; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

        /* XML-Enhanced Workflow Display */
        .xml-enhanced { border-left: 2px solid var(--vscode-charts-blue); }
        .xml-badge { font-size: 9px; padding: 1px 4px; background: var(--vscode-charts-blue); color: white; border-radius: 3px; margin-left: 4px; }
        .xml-summary { font-size: 10px; margin-top: 4px; padding: 4px; background: var(--vscode-editor-background); border-radius: 3px; color: var(--vscode-foreground); opacity: 0.9; }
        .findings-list { margin-top: 4px; }
        .finding-item { display: flex; align-items: center; gap: 4px; font-size: 10px; padding: 2px 0; }
        .severity-badge { font-size: 8px; padding: 1px 4px; border-radius: 2px; font-weight: bold; }
        .severity-badge.critical { background: #ff4444; color: white; }
        .severity-badge.high { background: #ff8800; color: white; }
        .severity-badge.medium { background: #ffcc00; color: black; }
        .severity-badge.low { background: #44aa44; color: white; }
        .severity-badge.info { background: #4488cc; color: white; }
        .finding-title { opacity: 0.9; }
        .checklist-list { margin-top: 4px; }
        .checklist-item { font-size: 10px; opacity: 0.8; padding: 1px 0; }

        /* Buttons */
        .btn {
            padding: 6px 12px;
            background: var(--button-bg);
            color: var(--button-fg);
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
        }

        .btn:hover { opacity: 0.9; }

        .btn-row {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }

        /* Status Badge */
        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 500;
        }

        .badge.success { background: rgba(16, 185, 129, 0.2); color: var(--success); }
        .badge.warning { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
        .badge.error { background: rgba(239, 68, 68, 0.2); color: var(--error); }
        .badge.info { background: rgba(99, 102, 241, 0.2); color: #6366f1; }

        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 24px;
            opacity: 0.7;
        }
        .empty-state .icon {
            font-size: 32px;
            display: block;
            margin-bottom: 8px;
        }
        .empty-state .hint {
            font-size: 11px;
            opacity: 0.6;
            margin-top: 4px;
        }

        /* Error Banner */
        #error-banner {
            background: var(--vscode-inputValidation-errorBackground);
            border: 1px solid var(--vscode-inputValidation-errorBorder);
            padding: 8px;
            margin: 8px 0;
            border-radius: 4px;
            font-size: 11px;
            display: none;
        }
        #error-banner .error-item {
            margin: 4px 0;
        }

        /* Progress Bars */
        .progress-bar {
            height: 6px;
            background: var(--border);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 4px;
        }

        .progress-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 0.3s;
        }

        .progress-fill.success { background: var(--success); }
        .progress-fill.warning { background: var(--warning); }
        .progress-fill.error { background: var(--error); }

        /* Action Buttons Grid */
        .actions-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 6px;
        }

        .action-btn {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 10px 6px;
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: 1px solid var(--border);
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s;
            font-size: 11px;
        }

        .action-btn:hover {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border-color: var(--vscode-button-background);
        }

        .action-icon {
            font-size: 18px;
            margin-bottom: 2px;
        }

        .slash-cmd {
            font-size: 11px;
            color: var(--vscode-editor-foreground, #000);
            font-family: var(--vscode-editor-font-family, monospace);
            margin-top: 2px;
        }

        /* Health Tree View */
        .health-tree {
            padding: 0 8px;
        }

        .tree-item {
            display: flex;
            align-items: center;
            padding: 6px 8px;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.15s;
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

        /* Workflow Selector */
        .workflow-selector {
            display: flex;
            gap: 8px;
            align-items: center;
        }

        .workflow-dropdown {
            flex: 1;
            padding: 6px 8px;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border: 1px solid var(--border);
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
        }

        .workflow-dropdown:focus {
            outline: 1px solid var(--vscode-focusBorder);
        }

        .workflow-run-btn {
            padding: 6px 12px;
            white-space: nowrap;
        }

        /* Workflow grid - 2 columns for longer labels */
        .workflow-grid {
            grid-template-columns: repeat(2, 1fr);
        }

        .workflow-btn {
            flex-direction: row;
            justify-content: flex-start;
            gap: 8px;
            padding: 8px 10px;
        }

        .workflow-btn .action-icon {
            margin-bottom: 0;
            font-size: 16px;
        }

        .new-workflow-btn {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }
        .new-workflow-btn:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }
        .new-workflow-btn-large {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .new-workflow-btn-large:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }
    </style>
</head>
<body>
    <div id="error-banner"></div>

    <!-- Health Summary Bar -->
    <div class="card" style="margin-bottom: 12px; cursor: pointer;" onclick="openHealthPanel()" title="Click to view detailed health metrics">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="font-size: 12px; font-weight: 600;">Health:</span>
                <span id="health-score-summary" style="font-size: 14px; font-weight: 700; margin-left: 8px;">--</span>
            </div>
        </div>
    </div>

        <div class="card" style="margin-top: 12px">
            <div class="card-title">Workflows</div>

            <!-- Code Review -->
            <div style="margin-top: 8px; margin-bottom: 4px; font-size: 10px; opacity: 0.6; font-weight: 600;">📝 CODE REVIEW</div>
            <div class="actions-grid workflow-grid">
                <button class="action-btn workflow-btn" data-workflow="code-review" title="Review any code via /review skill - enforces coding standards and best practices">
                    <span class="action-icon">&#x1F50D;</span>
                    <span>Review Code</span>
                    <span class="slash-cmd">/review</span>
                </button>
                <button class="action-btn workflow-btn" data-workflow="pr-review" title="Review pull requests via /review-pr skill - code quality + security with verdict">
                    <span class="action-icon">&#x1F4C4;</span>
                    <span>Review PR</span>
                    <span class="slash-cmd">/review-pr</span>
                </button>
            </div>

            <!-- Development -->
            <div style="margin-top: 12px; margin-bottom: 4px; font-size: 10px; opacity: 0.6; font-weight: 600;">🛠️ DEVELOPMENT</div>
            <div class="actions-grid workflow-grid" style="grid-template-columns: repeat(2, 1fr);">
                <button class="action-btn workflow-btn" data-workflow="bug-predict" title="Debug issues via /debug skill - analyze errors and find root causes">
                    <span class="action-icon">&#x1F41B;</span>
                    <span>Debug</span>
                    <span class="slash-cmd">/debug</span>
                </button>
                <button class="action-btn workflow-btn" data-workflow="refactor-plan" title="Refactoring assistant via /refactor skill - safe code improvements">
                    <span class="action-icon">&#x1F3D7;</span>
                    <span>Refactor</span>
                    <span class="slash-cmd">/refactor</span>
                </button>
                <button class="action-btn skill-btn" data-skill="/explain" title="Explain code via /explain skill - understand architecture and patterns">
                    <span class="action-icon">&#x1F4A1;</span>
                    <span>Explain</span>
                    <span class="slash-cmd">/explain</span>
                </button>
            </div>
            <div class="actions-grid workflow-grid" style="grid-template-columns: repeat(2, 1fr); margin-top: 6px;">
                <button class="action-btn workflow-btn dynamic-create-btn" data-create-type="agent" title="Create a custom AI agent with Socratic-guided questions">
                    <span class="action-icon">&#x1F916;</span>
                    <span>New Agent</span>
                    <span class="slash-cmd">/create-agent</span>
                </button>
                <button class="action-btn workflow-btn dynamic-create-btn" data-create-type="team" title="Create a custom AI agent team with Socratic-guided workflow">
                    <span class="action-icon">&#x1F465;</span>
                    <span>New Agent Team</span>
                    <span class="slash-cmd">/create-team</span>
                </button>
            </div>

            <!-- Security & Performance -->
            <div style="margin-top: 12px; margin-bottom: 4px; font-size: 10px; opacity: 0.6; font-weight: 600;">🔒 SECURITY & PERFORMANCE</div>
            <div class="actions-grid workflow-grid" style="grid-template-columns: repeat(2, 1fr);">
                <button class="action-btn workflow-btn" data-workflow="security-audit" title="Security scan via /security-scan skill - OWASP checks and vulnerability detection">
                    <span class="action-icon">&#x1F512;</span>
                    <span>Security</span>
                    <span class="slash-cmd">/security-scan</span>
                </button>
                <button class="action-btn workflow-btn" data-workflow="perf-audit" title="Performance profiling via /profile skill - identify bottlenecks and hot paths">
                    <span class="action-icon">&#x26A1;</span>
                    <span>Profile</span>
                    <span class="slash-cmd">/profile</span>
                </button>
                <button class="action-btn workflow-btn" data-workflow="dependency-check" title="Dependency audit via /deps skill - CVE scanning, outdated packages, license compliance">
                    <span class="action-icon">&#x1F4E6;</span>
                    <span>Deps</span>
                    <span class="slash-cmd">/deps</span>
                </button>
            </div>

            <!-- Testing -->
            <div style="margin-top: 12px; margin-bottom: 4px; font-size: 10px; opacity: 0.6; font-weight: 600;">🧪 TESTING</div>
            <div class="actions-grid workflow-grid" style="grid-template-columns: repeat(2, 1fr);">
                <button class="action-btn workflow-btn" id="btn-test-gen-direct" data-workflow="test-gen" title="Generate comprehensive test suites with smart coverage analysis">
                    <span class="action-icon">&#x1F9EA;</span>
                    <span>Gen Tests</span>
                    <span class="slash-cmd">/test</span>
                </button>
                <button class="action-btn workflow-btn agent-team-btn" data-skill="/test-coverage" data-template="test-coverage-boost" title="Boost test coverage via /test-coverage skill">
                    <span class="action-icon">&#x1F3AF;</span>
                    <span>Coverage</span>
                    <span class="slash-cmd">/test-coverage</span>
                </button>
                <button class="action-btn workflow-btn agent-team-btn" data-skill="/test-maintenance" data-template="test-maintenance" title="Maintain test health - analyze, fix, and validate tests">
                    <span class="action-icon">&#x1F527;</span>
                    <span>Maintenance</span>
                    <span class="slash-cmd">/test-maintenance</span>
                </button>
                <button class="action-btn skill-btn" data-skill="/benchmark" title="Performance benchmarking via /benchmark skill - track regressions over time">
                    <span class="action-icon">&#x1F4CA;</span>
                    <span>Benchmark</span>
                    <span class="slash-cmd">/benchmark</span>
                </button>
            </div>

            <!-- Documentation -->
            <div style="margin-top: 12px; margin-bottom: 4px; font-size: 10px; opacity: 0.6; font-weight: 600;">📚 DOCUMENTATION</div>
            <div class="actions-grid workflow-grid">
                <button class="action-btn workflow-btn" data-workflow="doc-orchestrator" title="End-to-end documentation management: scout gaps, prioritize, and generate">
                    <span class="action-icon">&#x1F4DA;</span>
                    <span>Manage Docs</span>
                    <span class="slash-cmd">/manage-docs</span>
                </button>
                <button class="action-btn workflow-btn" data-workflow="doc-gen" title="Cost-optimized documentation generation: outline → write → polish">
                    <span class="action-icon">&#x1F4DD;</span>
                    <span>Generate Docs</span>
                    <span class="slash-cmd">/feature-overview</span>
                </button>
            </div>

            <!-- Git & Release -->
            <div style="margin-top: 12px; margin-bottom: 4px; font-size: 10px; opacity: 0.6; font-weight: 600;">🚀 GIT & RELEASE</div>
            <div class="actions-grid workflow-grid" style="grid-template-columns: repeat(2, 1fr);">
                <button class="action-btn workflow-btn skill-btn" data-skill="/commit" title="Create well-formatted commits via /commit skill">
                    <span class="action-icon">&#x1F4BE;</span>
                    <span>Commit</span>
                    <span class="slash-cmd">/commit</span>
                </button>
                <button class="action-btn workflow-btn skill-btn" data-skill="/pr" title="Create pull requests via /pr skill - structured descriptions">
                    <span class="action-icon">&#x1F500;</span>
                    <span>Create PR</span>
                    <span class="slash-cmd">/pr</span>
                </button>
                <button class="action-btn workflow-btn agent-team-btn" data-skill="/release-prep" data-template="release-prep" title="Full release preparation via /release-prep skill">
                    <span class="action-icon">&#x1F680;</span>
                    <span>Release</span>
                    <span class="slash-cmd">/release-prep</span>
                </button>
            </div>


        </div>

        <!-- Workflow Results Panel (hidden by default) -->
        <div id="workflow-results" class="card" style="margin-top: 12px; display: none;">
            <div class="card-title" style="display: flex; justify-content: space-between; align-items: center;">
                <span id="workflow-results-title">&#x2699; Workflow Results</span>
                <button id="close-workflow-results" style="background: none; border: none; cursor: pointer; font-size: 14px; opacity: 0.7;">&#x2715;</button>
            </div>
            <!-- Input Section -->
            <div id="workflow-input-section" style="margin-bottom: 10px;">
                <div id="workflow-input-label" style="font-size: 11px; margin-bottom: 4px; opacity: 0.8;">Enter your query:</div>
                <div id="workflow-text-input" style="display: block;">
                    <textarea id="workflow-input" placeholder="e.g., What are the best practices for error handling?" style="width: 100%; height: 60px; padding: 8px; font-size: 11px; font-family: var(--vscode-font-family); background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--border); border-radius: 4px; resize: vertical;"></textarea>
                </div>
                <div id="workflow-file-input" style="display: none;">
                    <div style="display: flex; gap: 6px; align-items: center;">
                        <input id="workflow-path" type="text" placeholder="Click Browse..." readonly style="flex: 1; padding: 8px; font-size: 11px; font-family: var(--vscode-font-family); background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--border); border-radius: 4px;">
                        <button id="workflow-browse-btn" class="btn" style="white-space: nowrap;">&#x1F4C2; Browse</button>
                    </div>
                    <div id="workflow-project-row" style="display: none; margin-top: 6px;">
                        <button id="workflow-project-root-btn" class="btn" style="width: 100%; background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground);" title="Use entire project folder">
                            &#x1F4C1; Use Entire Project
                        </button>
                    </div>
                </div>
                <div id="workflow-dropdown-input" style="display: none; text-align: center; padding: 10px;">
                    <button id="workflow-select-btn" class="btn" style="width: 100%;">&#x25BC; Select Option</button>
                </div>
                <!-- Cost Estimate Display -->
                <div id="workflow-cost-estimate" style="display: none; margin-top: 8px; padding: 8px; background: var(--vscode-editor-background); border: 1px solid var(--border); border-radius: 4px; font-size: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="opacity: 0.7;">Estimated Cost:</span>
                        <span id="cost-estimate-value" style="font-weight: 600; color: var(--vscode-charts-blue);">--</span>
                    </div>
                    <div id="cost-estimate-details" style="margin-top: 4px; opacity: 0.6; font-size: 9px;"></div>
                </div>
                <button id="workflow-run-btn" class="btn" style="margin-top: 8px; width: 100%;">&#x25B6; Run Workflow</button>
            </div>
            <!-- Real-time Progress Display -->
            <div id="workflow-progress" style="display: none; margin-bottom: 8px; padding: 10px; background: var(--vscode-editor-background); border: 1px solid var(--border); border-radius: 4px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span id="progress-stage" style="font-size: 11px; font-weight: 500;">Stage 1/3</span>
                    <span id="progress-cost" style="font-size: 10px; opacity: 0.7;">$0.0000</span>
                </div>
                <div class="progress-bar" style="height: 8px; margin-bottom: 4px;">
                    <div id="progress-fill" class="progress-fill success" style="width: 0%; transition: width 0.3s;"></div>
                </div>
                <div id="progress-message" style="font-size: 10px; opacity: 0.7;">Starting...</div>
            </div>
            <div id="workflow-results-status" style="margin-bottom: 8px; padding: 6px 10px; border-radius: 4px; font-size: 11px; display: none;">
                Running...
            </div>
            <div id="workflow-results-content" style="max-height: 300px; overflow-y: auto; font-family: var(--vscode-editor-font-family); font-size: 11px; line-height: 1.5; white-space: pre-wrap; background: var(--vscode-editor-background); padding: 10px; border-radius: 4px; border: 1px solid var(--border); display: none;">
            </div>
            <!-- Report Action Button -->
            <div id="workflow-actions" style="display: none; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border);">
                <button id="ask-claude-btn" class="btn" style="width: 100%; font-size: 10px; padding: 6px 8px; background: var(--vscode-button-background); color: var(--vscode-button-foreground);" title="Copy report with prompt to clipboard">
                    &#x1F4AC; Ask Claude
                </button>
            </div>
        </div>

        <div style="margin-top: 12px; text-align: center;">
            <button class="btn" id="open-web-dashboard" style="opacity: 0.7; font-size: 10px;">&#x1F310; Open Full Web Dashboard</button>
        </div>

    <script nonce="${nonce}">
        console.log('[EmpathyDashboard] WEBVIEW SCRIPT LOADED - VERSION 4 - TEST GEN FIX');
        const vscode = acquireVsCodeApi();
        const PROJECT_PATH = '${projectPath}';

        // Track running actions to prevent duplicate clicks
        const runningActions = new Set();

        // Button click handlers - use event delegation for CSP compliance
        document.querySelectorAll('button[data-cmd]').forEach(btn => {
            btn.addEventListener('click', function() {
                const cmd = this.dataset.cmd;

                // Prevent duplicate action
                if (runningActions.has(cmd)) {
                    return;
                }
                runningActions.add(cmd);

                // Store original content and show running state
                const iconSpan = this.querySelector('.action-icon');
                const textSpan = this.querySelector('span:not(.action-icon)');
                const originalIcon = iconSpan ? iconSpan.innerHTML : '';
                const originalText = textSpan ? textSpan.textContent : this.textContent;

                this.disabled = true;
                this.style.opacity = '0.7';
                if (iconSpan) iconSpan.innerHTML = '&#x23F3;'; // Hourglass
                if (textSpan) textSpan.textContent = 'Running...';
                else this.textContent = 'Running...';

                vscode.postMessage({ type: 'runCommand', command: cmd });

                // Restore after timeout (command execution happens in terminal)
                setTimeout(() => {
                    this.disabled = false;
                    this.style.opacity = '1';
                    if (iconSpan) iconSpan.innerHTML = originalIcon;
                    if (textSpan) textSpan.textContent = originalText;
                    runningActions.delete(cmd);
                }, 3000);
            });
        });

        // Tree item click handlers
        document.querySelectorAll('.tree-item[data-cmd]').forEach(item => {
            item.addEventListener('click', function() {
                const cmd = this.dataset.cmd;
                if (runningActions.has('tree-' + cmd)) return;
                runningActions.add('tree-' + cmd);

                this.style.opacity = '0.5';
                vscode.postMessage({ type: 'runCommand', command: cmd });

                setTimeout(() => {
                    this.style.opacity = '1';
                    runningActions.delete('tree-' + cmd);
                }, 3000);
            });
        });

        // Store original button content for restoration
        const workflowButtonState = new Map();
        let currentWorkflow = null;
        let workflowLastInputs = {}; // Persisted workflow inputs
        let lastReportData = null; // Store last workflow report for copy/ask actions

        // Workflow input configuration - defines input type and UI for each workflow
        const workflowConfig = {
            'code-review': {
                type: 'file',
                label: 'Select file to review',
                placeholder: 'Click Browse or type path...',
                allowText: true  // hybrid - allows manual path entry too
            },
            'doc-orchestrator': {
                type: 'folder',
                label: 'Select folder to analyze for documentation',
                placeholder: 'Click Browse or leave empty for project root...',
                allowText: true
            },
            'bug-predict': {
                type: 'folder',
                label: 'Select folder to analyze for bugs',
                placeholder: 'Click Browse to select folder...'
            },
            'security-audit': {
                type: 'folder',
                label: 'Select folder to audit',
                placeholder: 'Click Browse to select folder...'
            },
            'perf-audit': {
                type: 'folder',
                label: 'Select folder to profile',
                placeholder: 'Click Browse to select folder...'
            },
            'test-gen': {
                type: 'folder',
                label: 'Select folder to analyze for test gaps',
                placeholder: 'Click Browse to select folder...'
            },
            'refactor-plan': {
                type: 'folder',
                label: 'Select folder to plan refactoring',
                placeholder: 'Click Browse to select folder...'
            },
            'dependency-check': {
                type: 'dropdown',
                label: 'Select dependency check scope',
                options: ['All dependencies', 'Security-critical only', 'Outdated only', 'Direct dependencies only']
            },
            'health-check': {
                type: 'text',
                label: 'Path to check (or . for current)',
                placeholder: 'e.g., src/ or .'
            },
            'pro-review': {
                type: 'file',
                label: 'Select file or paste code diff to review',
                placeholder: 'Click Browse or paste code diff...',
                allowText: true
            },
            'pr-review': {
                type: 'folder',
                label: 'Select folder containing PR changes',
                placeholder: 'Click Browse to select folder...'
            },
            'health-check': {
                type: 'folder',
                label: 'Select folder to check health',
                placeholder: 'Click Browse or use Project button...'
            }
        };

        // Helper to show the appropriate input type
        function showInputType(type, config) {
            const textInput = document.getElementById('workflow-text-input');
            const fileInput = document.getElementById('workflow-file-input');
            const dropdownInput = document.getElementById('workflow-dropdown-input');
            const pathField = document.getElementById('workflow-path');
            const textField = document.getElementById('workflow-input');

            // Get last input for this workflow (if any)
            const lastInput = workflowLastInputs[currentWorkflow] || '';

            // Hide all first
            textInput.style.display = 'none';
            fileInput.style.display = 'none';
            dropdownInput.style.display = 'none';

            if (type === 'text') {
                textInput.style.display = 'block';
                textField.placeholder = config.placeholder || 'Enter your query...';
                textField.value = lastInput; // Pre-populate with last input
                textField.focus();
            } else if (type === 'file' || type === 'folder') {
                fileInput.style.display = 'block';
                pathField.placeholder = config.placeholder || 'Click Browse...';
                // If hybrid (allowText), make editable
                pathField.readOnly = !config.allowText;
                // Show "Use Entire Project" row for both file and folder type workflows
                const projectRow = document.getElementById('workflow-project-row');
                if (projectRow) {
                    projectRow.style.display = 'block';
                }

                if (type === 'folder') {
                    // For folders: default to full project path unless user has history
                    pathField.value = lastInput || PROJECT_PATH;
                    pathField.placeholder = 'Project path or Browse...';
                } else {
                    // For files: default to project path or use history
                    pathField.value = lastInput || PROJECT_PATH;
                    if (!lastInput) {
                        vscode.postMessage({ type: 'getActiveFile', workflow: currentWorkflow });
                    }
                }
            } else if (type === 'dropdown') {
                dropdownInput.style.display = 'block';
                // Pre-populate dropdown if we have history
                if (lastInput) {
                    selectedDropdownValue = lastInput;
                    const selectBtn = document.getElementById('workflow-select-btn');
                    selectBtn.textContent = lastInput;
                }
            }
        }

        // Direct handler for test-gen button (bypasses general workflow handler)
        const testGenBtn = document.getElementById('btn-test-gen-direct');
        if (testGenBtn) {
            console.log('[EmpathyDashboard] Found test-gen button, attaching direct handler');
            testGenBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                console.log('[EmpathyDashboard] Test-gen button clicked directly');
                vscode.postMessage({ type: 'openTestGenerator' });
            });
        } else {
            console.log('[EmpathyDashboard] WARNING: test-gen button not found!');
        }

        // Meta-Orchestration v4.0 button handlers - run CrewAI workflows
        const healthCheckBtn = document.getElementById('btn-health-check-v4');
        if (healthCheckBtn) {
            healthCheckBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                console.log('[EmpathyDashboard] Health Check v4 clicked - running workflow');
                vscode.postMessage({ type: 'runOrchestratedHealthCheck' });
            });
        }

        const releasePrepBtn = document.getElementById('btn-release-prep-v4');
        if (releasePrepBtn) {
            releasePrepBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                console.log('[EmpathyDashboard] Release Prep v4 clicked - running workflow');
                vscode.postMessage({ type: 'runOrchestratedReleasePrep' });
            });
        }

        // AI Agent Team button handlers (v4.4) - Copy skill and suggest Claude Code
        document.querySelectorAll('.agent-team-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const skill = this.dataset.skill;
                const template = this.dataset.template;
                const label = this.querySelector('span:not(.action-icon)').textContent;
                console.log('[EmpathyDashboard] Agent team button clicked:', template);
                vscode.postMessage({
                    type: 'runAgentTeam',
                    skill: skill,
                    template: template,
                    label: label
                });
            });
        });

        // v4.6.3: Skill button handlers - run skill directly via Claude Code
        document.querySelectorAll('.skill-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const skill = this.dataset.skill;
                const label = this.querySelector('span:not(.action-icon)').textContent;
                console.log('[EmpathyDashboard] Skill button clicked:', skill);
                vscode.postMessage({
                    type: 'runSkill',
                    skill: skill,
                    label: label
                });
            });
        });

        // Dynamic Agent/Team creation button handlers (v4.4) - Socratic-guided creation
        document.querySelectorAll('.dynamic-create-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const createType = this.dataset.createType;
                console.log('[EmpathyDashboard] Dynamic create button clicked:', createType);
                vscode.postMessage({
                    type: 'createDynamic',
                    createType: createType
                });
            });
        });

        // Workflow button click handlers - show input panel first
        const workflowBtns = document.querySelectorAll('.action-btn[data-workflow]');
        console.log('[EmpathyDashboard] Found workflow buttons:', workflowBtns.length);
        workflowBtns.forEach(btn => {
            const workflow = btn.dataset.workflow;
            const iconSpan = btn.querySelector('.action-icon');
            const textSpan = btn.querySelector('span:not(.action-icon)');
            workflowButtonState.set(workflow, {
                icon: iconSpan ? iconSpan.innerHTML : '',
                text: textSpan ? textSpan.textContent : '',
                btn: btn
            });

            btn.addEventListener('click', function() {
                const wf = this.dataset.workflow;
                console.log('[EmpathyDashboard] Workflow button clicked:', wf);
                currentWorkflow = wf;

                // Special case: doc-orchestrator opens the Documentation Analysis panel directly
                if (wf === 'doc-orchestrator') {
                    vscode.postMessage({ type: 'openDocAnalysis' });
                    return;
                }

                // Meta-Orchestration v4.0: Handled by direct button click handlers above
                // (No special routing needed here - buttons send specific message types)

                // Report workflows: run immediately with project root and open in editor
                const reportWorkflows = [
                    'code-review', 'bug-predict', 'security-audit', 'perf-audit',
                    'refactor-plan', 'health-check', 'pr-review', 'pro-review',
                    'doc-gen',  // Doc generation workflow runs immediately
                    'test-gen',  // Test generation workflow runs immediately
                    'dependency-check',  // Dependency check workflow runs immediately
                    'release-prep',  // Release prep workflow runs immediately
                    'secure-release'  // Secure release workflow runs immediately
                ];
                if (reportWorkflows.includes(wf)) {
                    // Run workflow immediately with project root as input
                    console.log('[EmpathyDashboard] Running report workflow in editor:', wf);
                    vscode.postMessage({ type: 'runWorkflowInEditor', workflow: wf, input: '.' });
                    return;
                }

                // Show input panel for other workflows
                const resultsPanel = document.getElementById('workflow-results');
                const resultsTitle = document.getElementById('workflow-results-title');
                const inputSection = document.getElementById('workflow-input-section');
                const inputLabel = document.getElementById('workflow-input-label');
                const resultsStatus = document.getElementById('workflow-results-status');
                const resultsContent = document.getElementById('workflow-results-content');

                const config = workflowConfig[wf] || { type: 'text', label: 'Enter your query:', placeholder: 'Describe what you need...' };

                resultsPanel.style.display = 'block';
                resultsTitle.innerHTML = '&#x2699; ' + wf;
                inputSection.style.display = 'block';
                inputLabel.textContent = config.label;
                resultsStatus.style.display = 'none';
                resultsContent.style.display = 'none';
                resultsContent.textContent = '';

                // Show correct input type
                showInputType(config.type, config);
            });
        });

        // New Workflow buttons - opens the Workflow Wizard panel
        const newWorkflowBtn = document.getElementById('btn-new-workflow');
        if (newWorkflowBtn) {
            newWorkflowBtn.addEventListener('click', function() {
                vscode.postMessage({ type: 'openWorkflowWizard' });
            });
        }
        const newWorkflowBtnTab = document.getElementById('btn-new-workflow-tab');
        if (newWorkflowBtnTab) {
            newWorkflowBtnTab.addEventListener('click', function() {
                vscode.postMessage({ type: 'openWorkflowWizard' });
            });
        }

        // Browse button click handler
        const browseBtn = document.getElementById('workflow-browse-btn');
        if (browseBtn) {
            browseBtn.addEventListener('click', function() {
                if (!currentWorkflow) return;
                const config = workflowConfig[currentWorkflow];
                if (config && config.type === 'folder') {
                    vscode.postMessage({ type: 'showFolderPicker', workflow: currentWorkflow });
                } else {
                    vscode.postMessage({ type: 'showFilePicker', workflow: currentWorkflow });
                }
            });
        }

        // Project Root button click handler - sets path to project root
        const projectRootBtn = document.getElementById('workflow-project-root-btn');
        if (projectRootBtn) {
            projectRootBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                if (!currentWorkflow) return;
                const pathField = document.getElementById('workflow-path');
                if (pathField) {
                    pathField.value = PROJECT_PATH;
                    pathField.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
        }

        // Select option button click handler (for dropdown)
        const selectBtn = document.getElementById('workflow-select-btn');
        if (selectBtn) {
            selectBtn.addEventListener('click', function() {
                if (!currentWorkflow) return;
                const config = workflowConfig[currentWorkflow];
                if (config && config.options) {
                    vscode.postMessage({ type: 'showDropdown', workflow: currentWorkflow, options: config.options });
                }
            });
        }

        // Track selected dropdown value
        let selectedDropdownValue = '';

        // Debounce helper for cost estimation
        let costEstimateTimeout = null;
        function requestCostEstimate(inputValue) {
            if (costEstimateTimeout) {
                clearTimeout(costEstimateTimeout);
            }
            costEstimateTimeout = setTimeout(function() {
                if (currentWorkflow && inputValue) {
                    vscode.postMessage({ type: 'estimateCost', workflow: currentWorkflow, input: inputValue });
                }
            }, 500);
        }

        // Add input listeners for cost estimation
        const workflowTextInput = document.getElementById('workflow-input');
        if (workflowTextInput) {
            workflowTextInput.addEventListener('input', function() {
                requestCostEstimate(this.value);
            });
        }

        const workflowPathInput = document.getElementById('workflow-path');
        if (workflowPathInput) {
            workflowPathInput.addEventListener('input', function() {
                requestCostEstimate(this.value);
            });
        }

        // Run workflow button handler
        const workflowRunBtn = document.getElementById('workflow-run-btn');
        if (workflowRunBtn) {
            workflowRunBtn.addEventListener('click', function() {
                if (!currentWorkflow) return;

                const config = workflowConfig[currentWorkflow] || { type: 'text' };
                let inputValue = '';

                // Get input value from appropriate field
                if (config.type === 'text') {
                    const inputField = document.getElementById('workflow-input');
                    inputValue = inputField.value.trim();
                    if (!inputValue) {
                        inputField.style.borderColor = 'var(--vscode-inputValidation-errorBorder)';
                        inputField.focus();
                        return;
                    }
                    inputField.style.borderColor = 'var(--border)';
                } else if (config.type === 'file' || config.type === 'folder') {
                    const pathField = document.getElementById('workflow-path');
                    inputValue = pathField.value.trim();
                    if (!inputValue) {
                        pathField.style.borderColor = 'var(--vscode-inputValidation-errorBorder)';
                        return;
                    }
                    pathField.style.borderColor = 'var(--border)';
                } else if (config.type === 'dropdown') {
                    inputValue = selectedDropdownValue;
                    if (!inputValue) {
                        const selectBtn = document.getElementById('workflow-select-btn');
                        selectBtn.style.borderColor = 'var(--vscode-inputValidation-errorBorder)';
                        return;
                    }
                }

                // Prevent duplicate action
                if (runningActions.has('wf-' + currentWorkflow)) {
                    return;
                }
                runningActions.add('wf-' + currentWorkflow);

                // Update button state
                const state = workflowButtonState.get(currentWorkflow);
                if (state) {
                    state.btn.disabled = true;
                    state.btn.style.opacity = '0.7';
                    const icon = state.btn.querySelector('.action-icon');
                    const text = state.btn.querySelector('span:not(.action-icon)');
                    if (icon) icon.innerHTML = '&#x23F3;';
                    if (text) text.textContent = 'Running...';
                }

                // Show running state
                const inputSection = document.getElementById('workflow-input-section');
                const resultsStatus = document.getElementById('workflow-results-status');
                const resultsContent = document.getElementById('workflow-results-content');
                const costEstimate = document.getElementById('workflow-cost-estimate');
                const progressPanel = document.getElementById('workflow-progress');

                inputSection.style.display = 'none';
                if (costEstimate) costEstimate.style.display = 'none';

                // Show progress panel for real-time updates
                if (progressPanel) {
                    progressPanel.style.display = 'block';
                    const progressStage = document.getElementById('progress-stage');
                    const progressFill = document.getElementById('progress-fill');
                    const progressMessage = document.getElementById('progress-message');
                    const progressCost = document.getElementById('progress-cost');
                    if (progressStage) progressStage.textContent = 'Starting...';
                    if (progressFill) { progressFill.style.width = '0%'; progressFill.className = 'progress-fill success'; }
                    if (progressMessage) progressMessage.textContent = 'Initializing workflow...';
                    if (progressCost) progressCost.textContent = '$0.0000';
                }

                resultsStatus.style.display = 'block';
                resultsStatus.style.background = 'rgba(99, 102, 241, 0.2)';
                resultsStatus.style.color = '#6366f1';
                resultsStatus.innerHTML = '&#x23F3; Running workflow...';
                resultsContent.style.display = 'block';
                resultsContent.innerHTML = '<div style="text-align: center; padding: 20px; opacity: 0.5;">Executing workflow with: ' + inputValue.substring(0, 50) + (inputValue.length > 50 ? '...' : '') + '</div>';

                vscode.postMessage({ type: 'runWorkflow', workflow: currentWorkflow, input: inputValue });
            });
        }

        // Close workflow results panel
        const closeWorkflowResults = document.getElementById('close-workflow-results');
        if (closeWorkflowResults) {
            closeWorkflowResults.addEventListener('click', function() {
                document.getElementById('workflow-results').style.display = 'none';
                currentWorkflow = null;
            });
        }

        // Ask Claude button - copy report with prompt to clipboard and open Claude Code
        const askClaudeBtn = document.getElementById('ask-claude-btn');
        if (askClaudeBtn) {
            askClaudeBtn.addEventListener('click', function() {
                if (!lastReportData) return;

                // Build the prompt with report
                const newline = String.fromCharCode(10);
                const workflowName = lastReportData.workflow || 'workflow';
                const metadata = [
                    '--- ' + workflowName + ' Report ---',
                    'Timestamp: ' + (lastReportData.timestamp || new Date().toISOString()),
                    'Cost: ' + (lastReportData.cost || 'N/A'),
                    'Duration: ' + (lastReportData.duration || 'N/A'),
                    '---',
                    ''
                ].join(newline);

                const prompt = 'Based on this ' + workflowName + ' report, please analyze the findings and suggest next steps:' + newline + newline + metadata + lastReportData.output;

                // Send to backend to copy and open Claude Code
                vscode.postMessage({ type: 'askClaude', content: prompt, workflow: workflowName });

                // Visual feedback
                const originalText = askClaudeBtn.innerHTML;
                askClaudeBtn.innerHTML = '&#x2714; Copied!';
                askClaudeBtn.style.background = 'rgba(16, 185, 129, 0.3)';
                setTimeout(() => {
                    askClaudeBtn.innerHTML = originalText;
                    askClaudeBtn.style.background = '';
                }, 2000);
            });
        }

        // View Costs button - switch to Costs tab and request data
        const viewCostsBtn = document.getElementById('view-costs-btn');

        if (viewCostsBtn) {
            viewCostsBtn.addEventListener('click', function() {
                // Switch to Costs tab
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                document.querySelector('.tab[data-tab="costs"]').classList.add('active');
                document.getElementById('tab-costs').classList.add('active');
                // Request cost data and model config
                vscode.postMessage({ type: 'getCosts' });
                vscode.postMessage({ type: 'getModelConfig' });
            });
        }

        // Open Web Dashboard button
        const openWebDashboardBtn = document.getElementById('open-web-dashboard');
        if (openWebDashboardBtn) {
            openWebDashboardBtn.addEventListener('click', function() {
                vscode.postMessage({ type: 'openWebDashboard' });
            });
        }

        // Panel opening functions
        function openHealthPanel() {
            vscode.postMessage({ type: 'openHealthPanel' });
        }

        function openCostsPanel() {
            vscode.postMessage({ type: 'openCostsPanel' });
        }

        function openWorkflowHistory() {
            vscode.postMessage({ type: 'openWorkflowHistory' });
        }

        // Handle data updates
        window.addEventListener('message', event => {
            const message = event.data;
            if (message.type === 'update') {
                updateHealth(message.data.health);
                updateWorkflows(message.data.workflows, message.data.workflowsEmpty);
                updateCosts(message.data.costs, message.data.costsEmpty);
                // Store workflow history for pre-population
                if (message.data.workflowLastInputs) {
                    workflowLastInputs = message.data.workflowLastInputs;
                }
                // Show error banner if there are errors
                showErrorBanner(message.data.errors);
            } else if (message.type === 'costsData') {
                updateCostsPanel(message.data);
            } else if (message.type === 'modelConfig') {
                updateModelConfig(message.data);
            } else if (message.type === 'workflowStatus') {
                updateWorkflowResults(message.data);
            } else if (message.type === 'pickerResult') {
                // Handle file/folder picker or dropdown result
                const data = message.data;
                if (data.cancelled) return;

                if (data.path) {
                    const config = workflowConfig[data.workflow];
                    if (config && config.type === 'dropdown') {
                        // Dropdown selection
                        selectedDropdownValue = data.path;
                        const selectBtn = document.getElementById('workflow-select-btn');
                        selectBtn.textContent = data.path;
                        selectBtn.style.borderColor = 'var(--border)';
                    } else {
                        // File or folder picker
                        const pathField = document.getElementById('workflow-path');
                        pathField.value = data.path;
                        pathField.style.borderColor = 'var(--border)';
                    }
                }
            } else if (message.type === 'activeFile') {
                // Pre-populate with active file if applicable
                const data = message.data;
                if (data.path && data.workflow === currentWorkflow) {
                    const config = workflowConfig[currentWorkflow];
                    // Only pre-populate for file pickers, not folders
                    if (config && config.type === 'file') {
                        const pathField = document.getElementById('workflow-path');
                        if (!pathField.value) {
                            pathField.value = data.path;
                        }
                    }
                }
            } else if (message.type === 'costEstimate') {
                // Display cost estimate for workflow
                updateCostEstimate(message.data);
            } else if (message.type === 'workflowProgress') {
                // Real-time progress update from WebSocket
                updateWorkflowProgress(message.data);
            }
        });

        // Update cost estimate display
        function updateCostEstimate(data) {
            const estimatePanel = document.getElementById('workflow-cost-estimate');
            const estimateValue = document.getElementById('cost-estimate-value');
            const estimateDetails = document.getElementById('cost-estimate-details');

            if (!estimatePanel || !estimateValue || !estimateDetails) return;

            if (data.error) {
                // Hide on error - estimation is optional
                estimatePanel.style.display = 'none';
                return;
            }

            if (data.estimate) {
                const est = data.estimate;
                estimatePanel.style.display = 'block';

                // Show cost range
                if (est.total_min !== undefined && est.total_max !== undefined) {
                    const minCost = est.total_min.toFixed(4);
                    const maxCost = est.total_max.toFixed(4);
                    estimateValue.textContent = minCost === maxCost ? '$' + minCost : '$' + minCost + ' - $' + maxCost;
                } else if (est.display) {
                    estimateValue.textContent = est.display;
                }

                // Show stage details
                if (est.stages && est.stages.length > 0) {
                    const stageInfo = est.stages.map(function(s) {
                        return s.name + ' (' + s.tier + '): ~' + s.tokens_estimate + ' tokens';
                    }).join(' | ');
                    estimateDetails.textContent = stageInfo;
                } else if (est.input_tokens) {
                    estimateDetails.textContent = 'Input: ~' + est.input_tokens + ' tokens | Provider: ' + (est.provider || 'default');
                }

                // Color by risk level
                if (est.risk === 'high') {
                    estimateValue.style.color = 'var(--vscode-charts-orange)';
                } else if (est.risk === 'medium') {
                    estimateValue.style.color = 'var(--vscode-charts-yellow)';
                } else {
                    estimateValue.style.color = 'var(--vscode-charts-green)';
                }
            }
        }

        // Update real-time progress display
        function updateWorkflowProgress(data) {
            const progressPanel = document.getElementById('workflow-progress');
            const progressStage = document.getElementById('progress-stage');
            const progressCost = document.getElementById('progress-cost');
            const progressFill = document.getElementById('progress-fill');
            const progressMessage = document.getElementById('progress-message');

            if (!progressPanel) return;

            if (data.status === 'running' || data.status === 'retrying' || data.status === 'fallback') {
                progressPanel.style.display = 'block';

                if (progressStage) {
                    progressStage.textContent = 'Stage ' + (data.stage_index + 1) + '/' + data.total_stages;
                }
                if (progressCost && data.cost_so_far !== undefined) {
                    progressCost.textContent = '$' + data.cost_so_far.toFixed(4);
                }
                if (progressFill && data.percent_complete !== undefined) {
                    progressFill.style.width = data.percent_complete + '%';
                }
                if (progressMessage) {
                    progressMessage.textContent = data.message || data.current_stage || 'Processing...';
                }

                // Update fill color based on status
                if (progressFill) {
                    if (data.status === 'fallback') {
                        progressFill.className = 'progress-fill warning';
                    } else if (data.status === 'retrying') {
                        progressFill.className = 'progress-fill warning';
                    } else {
                        progressFill.className = 'progress-fill success';
                    }
                }
            } else if (data.status === 'completed') {
                progressPanel.style.display = 'none';
            } else if (data.status === 'failed') {
                if (progressFill) {
                    progressFill.className = 'progress-fill error';
                }
                if (progressMessage) {
                    progressMessage.textContent = data.error || 'Failed';
                }
            }
        }

        function updateWorkflowResults(data) {
            const resultsPanel = document.getElementById('workflow-results');
            const resultsTitle = document.getElementById('workflow-results-title');
            const resultsStatus = document.getElementById('workflow-results-status');
            const resultsContent = document.getElementById('workflow-results-content');
            const actionsPanel = document.getElementById('workflow-actions');
            const progressPanel = document.getElementById('workflow-progress');

            // Hide progress panel on completion
            if (data.status !== 'running' && progressPanel) {
                progressPanel.style.display = 'none';
            }

            // Restore button state only on complete/error
            if (data.status !== 'running') {
                const state = workflowButtonState.get(data.workflow);
                if (state) {
                    state.btn.disabled = false;
                    state.btn.style.opacity = '1';
                    const icon = state.btn.querySelector('.action-icon');
                    const text = state.btn.querySelector('span:not(.action-icon)');
                    if (icon) icon.innerHTML = state.icon;
                    if (text) text.textContent = state.text;
                    runningActions.delete('wf-' + data.workflow);
                }
            }

            if (data.status === 'running') {
                resultsPanel.style.display = 'block';
                resultsTitle.innerHTML = '&#x2699; ' + data.workflow;
                resultsStatus.style.display = 'block';
                resultsStatus.style.background = 'rgba(99, 102, 241, 0.2)';
                resultsStatus.style.color = '#6366f1';
                resultsStatus.innerHTML = '&#x23F3; Running workflow...';
                resultsContent.innerHTML = '<div style="text-align: center; padding: 20px; opacity: 0.5;">Executing workflow...</div>';
                // Hide actions while running
                if (actionsPanel) actionsPanel.style.display = 'none';
            } else if (data.status === 'complete') {
                // If report was opened in editor, hide panel and show notification instead
                if (data.openedInEditor) {
                    resultsPanel.style.display = 'none';
                    currentWorkflow = null;
                    return;
                }

                resultsStatus.style.display = 'block';
                resultsStatus.style.background = 'rgba(16, 185, 129, 0.2)';
                resultsStatus.style.color = 'var(--vscode-testing-iconPassed)';
                resultsStatus.innerHTML = '&#x2714; Complete';

                // Check if output is crew workflow result (has verdict/quality_score)
                const crewWorkflows = ['pro-review', 'pr-review', 'health-check', 'release-prep', 'test-coverage-boost'];
                if (crewWorkflows.includes(data.workflow) || data.output.includes('"verdict"') || data.output.includes('"quality_score"')) {
                    try {
                        resultsContent.innerHTML = formatCrewOutput(data.output);
                    } catch (e) {
                        resultsContent.textContent = data.output || 'Workflow completed successfully.';
                    }
                } else {
                    resultsContent.textContent = data.output || 'Workflow completed successfully.';
                }

                // Store report data for copy/ask actions
                lastReportData = {
                    workflow: data.workflow,
                    output: data.output || '',
                    timestamp: new Date().toISOString(),
                    cost: data.cost || 'N/A',
                    duration: data.duration || 'N/A'
                };

                // Show action buttons
                if (actionsPanel) actionsPanel.style.display = 'block';
            } else if (data.status === 'error') {
                resultsStatus.style.display = 'block';
                resultsStatus.style.background = 'rgba(239, 68, 68, 0.2)';
                resultsStatus.style.color = 'var(--vscode-testing-iconFailed)';
                resultsStatus.innerHTML = '&#x2718; Error';
                resultsContent.textContent = data.output || data.error || 'An error occurred.';
                // Hide actions on error
                if (actionsPanel) actionsPanel.style.display = 'none';
                lastReportData = null;
            }
        }

        // Format crew workflow output with verdict badges, quality scores, etc.
        function formatCrewOutput(output) {
            // Try to parse JSON from output
            let data = null;
            try {
                // Try direct JSON parse
                data = JSON.parse(output);
            } catch (e) {
                // Try to extract JSON from output text
                const jsonMatch = output.match(/\\{[\\s\\S]*\\}/);
                if (jsonMatch) {
                    try {
                        data = JSON.parse(jsonMatch[0]);
                    } catch (e2) {}
                }
            }

            if (!data) {
                // Return formatted plain text if no JSON found
                return '<pre style="margin: 0;">' + escapeHtml(output) + '</pre>';
            }

            const verdictColors = {
                'approve': { bg: '#22c55e', color: 'white' },
                'approve_with_suggestions': { bg: '#eab308', color: 'black' },
                'request_changes': { bg: '#f97316', color: 'white' },
                'reject': { bg: '#ef4444', color: 'white' }
            };

            const agentIcons = {
                'lead': '&#x1F464;',
                'security': '&#x1F512;',
                'architecture': '&#x1F3DB;',
                'quality': '&#x2728;',
                'performance': '&#x26A1;',
                'hunter': '&#x1F50D;',
                'assessor': '&#x1F4CA;',
                'remediator': '&#x1F6E0;',
                'compliance': '&#x1F4CB;'
            };

            const severityColors = {
                'critical': '#ef4444',
                'high': '#f97316',
                'medium': '#eab308',
                'low': '#22c55e',
                'info': '#6b7280'
            };

            let html = '';

            // Verdict badge
            const verdict = data.verdict || data.go_no_go || '';
            if (verdict) {
                const vColors = verdictColors[verdict.toLowerCase()] || { bg: '#6b7280', color: 'white' };
                html += '<div style="margin-bottom: 12px;">';
                html += '<span style="display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: bold; background: ' + vColors.bg + '; color: ' + vColors.color + ';">';
                html += (verdict === 'approve' ? '&#x2714; ' : verdict === 'reject' ? '&#x2718; ' : '&#x26A0; ');
                html += verdict.replace(/_/g, ' ').toUpperCase();
                html += '</span></div>';
            }

            // Quality score meter
            const qualityScore = data.quality_score || data.combined_score;
            if (qualityScore !== undefined) {
                const scoreColor = qualityScore >= 80 ? '#22c55e' : qualityScore >= 60 ? '#eab308' : '#ef4444';
                html += '<div style="margin-bottom: 12px;">';
                html += '<div style="font-size: 10px; opacity: 0.7; margin-bottom: 4px;">Quality Score</div>';
                html += '<div style="display: flex; align-items: center; gap: 8px;">';
                html += '<div style="flex: 1; height: 8px; background: var(--vscode-widget-border); border-radius: 4px; overflow: hidden;">';
                html += '<div style="width: ' + qualityScore + '%; height: 100%; background: ' + scoreColor + ';"></div>';
                html += '</div>';
                html += '<span style="font-weight: bold; color: ' + scoreColor + ';">' + Math.round(qualityScore) + '/100</span>';
                html += '</div></div>';
            }

            // Agents used badges
            const agents = data.agents_used || [];
            if (agents.length > 0) {
                html += '<div style="margin-bottom: 12px;">';
                html += '<div style="font-size: 10px; opacity: 0.7; margin-bottom: 4px;">Agents Used</div>';
                html += '<div style="display: flex; flex-wrap: wrap; gap: 4px;">';
                agents.forEach(function(agent) {
                    const icon = agentIcons[agent.toLowerCase()] || '&#x1F916;';
                    html += '<span style="display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 10px; background: var(--vscode-badge-background); color: var(--vscode-badge-foreground);">';
                    html += icon + ' ' + agent;
                    html += '</span>';
                });
                html += '</div></div>';
            }

            // Findings summary
            const findings = data.findings || data.combined_findings || data.all_findings || [];
            const criticalCount = data.critical_count || findings.filter(function(f) { return f.severity === 'critical'; }).length;
            const highCount = data.high_count || findings.filter(function(f) { return f.severity === 'high'; }).length;

            if (findings.length > 0 || criticalCount > 0 || highCount > 0) {
                html += '<div style="margin-bottom: 12px;">';
                html += '<div style="font-size: 10px; opacity: 0.7; margin-bottom: 4px;">Findings (' + findings.length + ' total)</div>';
                html += '<div style="display: flex; gap: 12px; font-size: 11px;">';
                if (criticalCount > 0) html += '<span style="color: ' + severityColors.critical + ';">&#x2718; ' + criticalCount + ' critical</span>';
                if (highCount > 0) html += '<span style="color: ' + severityColors.high + ';">&#x26A0; ' + highCount + ' high</span>';
                html += '</div>';

                // Show top 5 findings
                if (findings.length > 0) {
                    html += '<div style="margin-top: 8px; max-height: 150px; overflow-y: auto;">';
                    findings.slice(0, 5).forEach(function(f) {
                        const sev = f.severity || 'medium';
                        const sevColor = severityColors[sev] || severityColors.medium;
                        html += '<div style="padding: 4px 0; border-bottom: 1px solid var(--vscode-widget-border); font-size: 10px;">';
                        html += '<span style="color: ' + sevColor + '; font-weight: bold;">[' + sev.toUpperCase() + ']</span> ';
                        html += escapeHtml(f.title || f.type || 'Issue');
                        if (f.file) html += ' <span style="opacity: 0.7;">(' + f.file + (f.line ? ':' + f.line : '') + ')</span>';
                        html += '</div>';
                    });
                    if (findings.length > 5) {
                        html += '<div style="opacity: 0.5; font-size: 10px; padding: 4px 0;">...and ' + (findings.length - 5) + ' more</div>';
                    }
                    html += '</div>';
                }
                html += '</div>';
            }

            // Summary text
            const summary = data.summary;
            if (summary) {
                html += '<div style="margin-top: 8px; padding: 8px; background: var(--vscode-editor-background); border-radius: 4px; font-size: 11px;">';
                html += escapeHtml(summary);
                html += '</div>';
            }

            // Blockers
            const blockers = data.blockers || [];
            if (blockers.length > 0) {
                html += '<div style="margin-top: 8px; padding: 8px; background: rgba(239, 68, 68, 0.1); border-radius: 4px; border: 1px solid rgba(239, 68, 68, 0.3);">';
                html += '<div style="font-weight: bold; color: #ef4444; margin-bottom: 4px;">&#x26D4; Blockers</div>';
                blockers.forEach(function(b) {
                    html += '<div style="font-size: 10px;">&#x2022; ' + escapeHtml(b) + '</div>';
                });
                html += '</div>';
            }

            // Duration & cost
            const duration = data.duration_seconds;
            const cost = data.cost;
            if (duration !== undefined || cost !== undefined) {
                html += '<div style="margin-top: 8px; font-size: 10px; opacity: 0.7;">';
                if (duration !== undefined) html += 'Duration: ' + duration.toFixed(1) + 's';
                if (cost !== undefined) html += (duration !== undefined ? ' | ' : '') + 'Cost: $' + cost.toFixed(4);
                html += '</div>';
            }

            return html || '<pre style="margin: 0;">' + escapeHtml(output) + '</pre>';
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text || '';
            return div.innerHTML;
        }

        // Chart rendering functions
        function renderCostTrendChart(dailyCosts) {
            const container = document.getElementById('cost-trend-chart');
            const labelsContainer = document.getElementById('cost-trend-labels');

            if (!dailyCosts || dailyCosts.length === 0) {
                container.innerHTML = '<div style="text-align: center; opacity: 0.5; width: 100%;">No daily data yet</div>';
                labelsContainer.innerHTML = '';
                return;
            }

            // Get last 7 days
            const last7 = dailyCosts.slice(-7);
            const maxCost = Math.max(...last7.map(d => d.cost), 0.01);

            const barHtml = last7.map((d, i) => {
                const height = Math.max((d.cost / maxCost) * 100, 2);
                const savingsHeight = Math.max((d.savings / maxCost) * 100, 0);
                return '<div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; height: 100%;" title="' + d.date + ': $' + d.cost.toFixed(4) + '">' +
                    '<div style="flex: 1; display: flex; flex-direction: column; justify-content: flex-end; width: 100%;">' +
                        '<div style="background: var(--vscode-charts-green); opacity: 0.4; height: ' + savingsHeight + '%; border-radius: 2px 2px 0 0;"></div>' +
                        '<div style="background: var(--vscode-charts-blue); height: ' + height + '%; border-radius: 0 0 2px 2px; min-height: 2px;"></div>' +
                    '</div>' +
                '</div>';
            }).join('');

            container.innerHTML = barHtml;

            // Show first and last date labels
            if (last7.length > 0) {
                const firstDate = last7[0].date.split('-').slice(1).join('/');
                const lastDate = last7[last7.length - 1].date.split('-').slice(1).join('/');
                labelsContainer.innerHTML = '<span>' + firstDate + '</span><span>' + lastDate + '</span>';
            }
        }

        function renderTierPieChart(byTier) {
            if (!byTier || Object.keys(byTier).length === 0) {
                document.getElementById('tier-cheap-pct').textContent = '--';
                document.getElementById('tier-capable-pct').textContent = '--';
                document.getElementById('tier-premium-pct').textContent = '--';
                return;
            }

            const cheap = byTier.cheap?.cost || 0;
            const capable = byTier.capable?.cost || 0;
            const premium = byTier.premium?.cost || 0;
            const total = cheap + capable + premium;

            if (total === 0) {
                document.getElementById('tier-cheap-pct').textContent = '0%';
                document.getElementById('tier-capable-pct').textContent = '0%';
                document.getElementById('tier-premium-pct').textContent = '0%';
                return;
            }

            const cheapPct = (cheap / total) * 100;
            const capablePct = (capable / total) * 100;
            const premiumPct = (premium / total) * 100;

            // Update pie chart using stroke-dasharray
            const circumference = 2 * Math.PI * 16; // r=16
            const pct = 100;

            const pieChaps = document.getElementById('pie-cheap');
            const pieCapa = document.getElementById('pie-capable');
            const piePrem = document.getElementById('pie-premium');

            if (pieChaps) {
                pieChaps.setAttribute('stroke-dasharray', (cheapPct * pct / 100) + ' ' + pct);
            }
            if (pieCapa) {
                pieCapa.setAttribute('stroke-dasharray', (capablePct * pct / 100) + ' ' + pct);
                pieCapa.setAttribute('stroke-dashoffset', '-' + (cheapPct * pct / 100));
            }
            if (piePrem) {
                piePrem.setAttribute('stroke-dasharray', (premiumPct * pct / 100) + ' ' + pct);
                piePrem.setAttribute('stroke-dashoffset', '-' + ((cheapPct + capablePct) * pct / 100));
            }

            // Update legend
            document.getElementById('tier-cheap-pct').textContent = cheapPct.toFixed(0) + '% ($' + cheap.toFixed(2) + ')';
            document.getElementById('tier-capable-pct').textContent = capablePct.toFixed(0) + '% ($' + capable.toFixed(2) + ')';
            document.getElementById('tier-premium-pct').textContent = premiumPct.toFixed(0) + '% ($' + premium.toFixed(2) + ')';
        }

        function renderProviderBars(byProvider) {
            const container = document.getElementById('provider-bars');

            if (!byProvider || Object.keys(byProvider).length === 0) {
                container.innerHTML = '<div style="text-align: center; opacity: 0.5; padding: 8px;">No provider data</div>';
                return;
            }

            // If only "unknown" provider, show message instead
            const keys = Object.keys(byProvider);
            if (keys.length === 1 && keys[0] === 'unknown') {
                container.innerHTML = '<div style="text-align: center; opacity: 0.5; padding: 8px;">Provider data not recorded in telemetry</div>';
                return;
            }

            const providerColors = {
                anthropic: '#d97706',
                openai: '#22c55e',
                google: '#4285f4',
                ollama: '#6366f1'
            };

            // Filter out "unknown" if there are other providers
            const entries = Object.entries(byProvider).filter(([p, _]) => p !== 'unknown');
            if (entries.length === 0) {
                container.innerHTML = '<div style="text-align: center; opacity: 0.5; padding: 8px;">No provider data</div>';
                return;
            }

            const maxCost = Math.max(...entries.map(([_, v]) => v.cost), 0.01);

            container.innerHTML = entries.map(([provider, data]) => {
                const width = Math.max((data.cost / maxCost) * 100, 5);
                const color = providerColors[provider.toLowerCase()] || '#888';
                return '<div style="display: flex; align-items: center; gap: 8px; font-size: 10px;">' +
                    '<div style="width: 60px; text-transform: capitalize;">' + provider + '</div>' +
                    '<div style="flex: 1; height: 16px; background: var(--vscode-input-background); border-radius: 2px; overflow: hidden;">' +
                        '<div style="width: ' + width + '%; height: 100%; background: ' + color + '; border-radius: 2px;"></div>' +
                    '</div>' +
                    '<div style="width: 60px; text-align: right;">$' + data.cost.toFixed(2) + '</div>' +
                '</div>';
            }).join('');
        }

        function updateCostsPanel(data) {
            // Update summary
            document.getElementById('costs-saved').textContent = '$' + (data.totalSavings || 0).toFixed(2);
            document.getElementById('costs-percent').textContent = (data.savingsPercent || 0) + '%';
            document.getElementById('costs-total').textContent = '$' + (data.totalCost || 0).toFixed(2);

            // Render charts
            renderCostTrendChart(data.dailyCosts);
            renderTierPieChart(data.byTier);
            renderProviderBars(data.byProvider);

            // Update requests list
            const listEl = document.getElementById('costs-list');
            if (!data.requests || data.requests.length === 0) {
                listEl.innerHTML = '<div style="text-align: center; padding: 20px; opacity: 0.5;">No requests yet</div>';
                return;
            }

            const tierColors = {
                cheap: '#22c55e',
                capable: '#3b82f6',
                premium: '#a855f7'
            };

            listEl.innerHTML = data.requests.map(req => {
                const tierColor = tierColors[req.tier] || '#888';
                const timeAgo = formatTimeAgo(req.timestamp);
                return '<div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--vscode-widget-border); font-size: 11px;">' +
                    '<div style="flex: 1;">' +
                        '<div style="font-weight: 500;">' + (req.task_type || 'unknown').replace(/_/g, ' ') + '</div>' +
                        '<div style="display: flex; gap: 8px; opacity: 0.7; font-size: 10px;">' +
                            '<span style="color: ' + tierColor + ';">' + (req.tier || 'capable') + '</span>' +
                            '<span>' + timeAgo + '</span>' +
                        '</div>' +
                    '</div>' +
                    '<div style="text-align: right;">' +
                        '<div style="color: var(--vscode-charts-green); font-weight: 500;">+$' + (req.savings || 0).toFixed(4) + '</div>' +
                        '<div style="opacity: 0.7; font-size: 10px;">$' + (req.actual_cost || 0).toFixed(4) + '</div>' +
                    '</div>' +
                '</div>';
            }).join('');
        }

        function updateModelConfig(data) {
            // Update provider and mode
            const providerEl = document.getElementById('current-provider');
            const modeEl = document.getElementById('current-mode');

            if (providerEl) {
                providerEl.textContent = data.provider || 'Unknown';
            }
            if (modeEl) {
                const modeLabels = {
                    'single': 'Single Provider',
                    'hybrid': 'Hybrid (Cost Optimized)',
                    'custom': 'Custom'
                };
                modeEl.textContent = modeLabels[data.mode] || data.mode || '--';
            }

            // Update tier models
            if (data.models) {
                const cheapEl = document.getElementById('model-cheap');
                const capableEl = document.getElementById('model-capable');
                const premiumEl = document.getElementById('model-premium');

                if (cheapEl) cheapEl.textContent = data.models.cheap || '--';
                if (capableEl) capableEl.textContent = data.models.capable || '--';
                if (premiumEl) premiumEl.textContent = data.models.premium || '--';
            }
        }

        function formatTimeAgo(timestamp) {
            if (!timestamp) return '';
            const now = new Date();
            const date = new Date(timestamp);
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);
            if (diffMins < 1) return 'just now';
            if (diffMins < 60) return diffMins + 'm ago';
            if (diffHours < 24) return diffHours + 'h ago';
            return diffDays + 'd ago';
        }

        function updateHealth(health) {
            // Guard against null health data
            if (!health) {
                document.getElementById('health-score-summary').textContent = '--';
                return;
            }

            const score = health.score || 0;

            // Update health summary bar
            const summaryEl = document.getElementById('health-score-summary');
            summaryEl.textContent = score + '%';
            summaryEl.style.color = score >= 80 ? 'var(--vscode-testing-iconPassed)' : score >= 50 ? 'var(--vscode-editorWarning-foreground)' : 'var(--vscode-testing-iconFailed)';
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

        // Workflow chart rendering functions
        function renderWorkflowTimeline(recentRuns) {
            const container = document.getElementById('workflow-timeline');

            if (!recentRuns || recentRuns.length === 0) {
                container.innerHTML = '<div style="text-align: center; opacity: 0.5; width: 100%;">No recent activity</div>';
                return;
            }

            // Group runs by hour buckets (last 24 hours = 24 slots)
            const now = new Date();
            const buckets = new Array(24).fill(null).map(() => ({ success: 0, failed: 0 }));

            for (const run of recentRuns) {
                if (!run.timestamp) continue;
                const runTime = new Date(run.timestamp);
                const hoursAgo = Math.floor((now - runTime) / 3600000);
                if (hoursAgo >= 0 && hoursAgo < 24) {
                    const bucketIdx = 23 - hoursAgo; // 0 = oldest, 23 = most recent
                    if (run.success) {
                        buckets[bucketIdx].success++;
                    } else {
                        buckets[bucketIdx].failed++;
                    }
                }
            }

            const maxCount = Math.max(...buckets.map(b => b.success + b.failed), 1);

            const barsHtml = buckets.map((bucket, i) => {
                const total = bucket.success + bucket.failed;
                if (total === 0) {
                    return '<div style="flex: 1; height: 100%; display: flex; align-items: flex-end;">' +
                        '<div style="width: 100%; height: 2px; background: var(--vscode-input-background); border-radius: 1px;"></div>' +
                    '</div>';
                }
                const height = Math.max((total / maxCount) * 100, 8);
                const successPct = (bucket.success / total) * 100;
                const color = bucket.failed > 0 ? 'linear-gradient(to top, var(--vscode-testing-iconFailed) ' + (100 - successPct) + '%, var(--vscode-testing-iconPassed) ' + (100 - successPct) + '%)' : 'var(--vscode-testing-iconPassed)';
                return '<div style="flex: 1; height: 100%; display: flex; align-items: flex-end;" title="' + total + ' run(s)">' +
                    '<div style="width: 100%; height: ' + height + '%; background: ' + color + '; border-radius: 2px; min-height: 4px;"></div>' +
                '</div>';
            }).join('');

            container.innerHTML = barsHtml;
        }

        function renderWorkflowCostBars(byWorkflow) {
            const container = document.getElementById('workflow-cost-bars');

            if (!byWorkflow || Object.keys(byWorkflow).length === 0) {
                container.innerHTML = '<div style="text-align: center; opacity: 0.5; padding: 8px;">No workflow data</div>';
                return;
            }

            const entries = Object.entries(byWorkflow).sort((a, b) => b[1].cost - a[1].cost);
            const maxCost = Math.max(...entries.map(([_, v]) => v.cost), 0.01);

            const workflowColors = {
                'security-audit': '#ef4444',
                'code-review': '#3b82f6',
                'bug-predict': '#f59e0b',
                'perf-audit': '#8b5cf6',
                'test-gen': '#22c55e',
                'doc-orchestrator': '#06b6d4',
                'refactor-plan': '#ec4899',
                'release-prep': '#6366f1'
            };

            container.innerHTML = entries.slice(0, 6).map(([workflow, data]) => {
                const width = Math.max((data.cost / maxCost) * 100, 5);
                const color = workflowColors[workflow] || '#888';
                const shortName = workflow.replace('-audit', '').replace('-gen', '').replace('-', ' ');
                return '<div style="display: flex; align-items: center; gap: 8px; font-size: 10px;">' +
                    '<div style="width: 70px; text-transform: capitalize; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="' + workflow + '">' + shortName + '</div>' +
                    '<div style="flex: 1; height: 14px; background: var(--vscode-input-background); border-radius: 2px; overflow: hidden;">' +
                        '<div style="width: ' + width + '%; height: 100%; background: ' + color + '; border-radius: 2px;"></div>' +
                    '</div>' +
                    '<div style="width: 50px; text-align: right;">$' + data.cost.toFixed(3) + '</div>' +
                '</div>';
            }).join('');
        }

        function updateWorkflows(workflows, isEmpty) {
            // Guard against null workflows data
            if (!workflows) {
                document.getElementById('wf-runs').textContent = '0';
                document.getElementById('wf-success').textContent = '0%';
                document.getElementById('wf-cost').textContent = '$0.00';
                document.getElementById('wf-savings').textContent = '$0.00';
                renderWorkflowTimeline([]);
                renderWorkflowCostBars({});
                return;
            }

            document.getElementById('wf-runs').textContent = workflows.totalRuns || 0;
            document.getElementById('wf-success').textContent = workflows.totalRuns > 0 ? Math.round((workflows.successfulRuns / workflows.totalRuns) * 100) + '%' : '0%';
            document.getElementById('wf-cost').textContent = '$' + workflows.totalCost.toFixed(4);
            document.getElementById('wf-savings').textContent = '$' + workflows.totalSavings.toFixed(4);

            // Render charts
            renderWorkflowTimeline(workflows.recentRuns);
            renderWorkflowCostBars(workflows.byWorkflow);

            const list = document.getElementById('workflows-list');

            // Check for empty state
            if (isEmpty || workflows.recentRuns.length === 0) {
                list.innerHTML = \`
                    <div class="empty-state">
                        <span class="icon">&#x1F4E6;</span>
                        <p>No workflow runs yet</p>
                        <p class="hint">Run a workflow from the Power tab to get started</p>
                    </div>
                \`;
                return;
            }

            list.innerHTML = workflows.recentRuns.slice(0, 10).map(run => {
                // Build XML summary section if available
                let xmlSection = '';
                if (run.xml_parsed && run.summary) {
                    xmlSection = \`<div class="xml-summary">\${run.summary}</div>\`;
                }
                // Build findings section if available
                let findingsSection = '';
                if (run.xml_parsed && run.findings && run.findings.length > 0) {
                    const findingsHtml = run.findings.slice(0, 3).map(f => \`
                        <div class="finding-item \${f.severity}">
                            <span class="severity-badge \${f.severity}">\${f.severity.toUpperCase()}</span>
                            <span class="finding-title">\${f.title}</span>
                        </div>
                    \`).join('');
                    findingsSection = \`<div class="findings-list">\${findingsHtml}</div>\`;
                }
                // Build checklist section if available
                let checklistSection = '';
                if (run.xml_parsed && run.checklist && run.checklist.length > 0) {
                    const checklistHtml = run.checklist.slice(0, 3).map(item => \`
                        <div class="checklist-item">&#x25A1; \${item}</div>
                    \`).join('');
                    checklistSection = \`<div class="checklist-list">\${checklistHtml}</div>\`;
                }

                return \`
                <div class="list-item \${run.xml_parsed ? 'xml-enhanced' : ''}">
                    <span class="list-item-icon">\${run.success ? '&#x2714;' : '&#x2718;'}</span>
                    <div class="list-item-content">
                        <div class="list-item-title">\${run.workflow}\${run.xml_parsed ? ' <span class="xml-badge">XML</span>' : ''}</div>
                        <div class="list-item-desc">Saved $\${run.savings.toFixed(4)}</div>
                        \${xmlSection}
                        \${findingsSection}
                        \${checklistSection}
                    </div>
                    <span class="badge \${run.success ? 'success' : 'error'}">\${run.success ? 'OK' : 'Failed'}</span>
                </div>
            \`;
            }).join('');
        }

        // --- Cost Simulator (Beta) ---

        // Per-request costs based on actual model pricing from registry
        // Assumes average request: ~1000 input tokens, ~500 output tokens
        // Formula: (1000/1M * input_cost) + (500/1M * output_cost)
        const SIM_TIER_PRICING = {
            // Haiku: $0.80/$4.00, Sonnet: $3.00/$15.00, Opus: $15.00/$75.00
            anthropic: { cheap: 0.0028, capable: 0.0105, premium: 0.0525 },
            // GPT-4o-mini: $0.15/$0.60, GPT-4o: $2.50/$10.00, o1: $15.00/$60.00
            openai: { cheap: 0.00045, capable: 0.0075, premium: 0.045 },
            // Flash: $0.10/$0.40, 1.5 Pro: $1.25/$5.00, 2.5 Pro: $1.25/$10.00
            google: { cheap: 0.0003, capable: 0.00375, premium: 0.00625 },
            // Cost-Optimized: Google cheap/capable + Anthropic premium (best quality where it matters)
            'cost-optimized': { cheap: 0.0003, capable: 0.00375, premium: 0.0525 },
            // Local models - no API cost
            ollama: { cheap: 0, capable: 0, premium: 0 }
        };

        // Scenario presets: total requests per week
        const SIM_SCENARIOS = {
            default: 200,
            heavy: 600,
            light: 60
        };

        function normalizeMix(cheap, capable, premium) {
            const total = cheap + capable + premium;
            if (!total || total <= 0) {
                return { cheap: 0.5, capable: 0.4, premium: 0.1 };
            }
            return {
                cheap: cheap / total,
                capable: capable / total,
                premium: premium / total
            };
        }

        function updateSliderLabels() {
            // Update slider value labels
            const cheapVal = document.getElementById('sim-cheap-val');
            const capableVal = document.getElementById('sim-capable-val');
            const premiumVal = document.getElementById('sim-premium-val');
            const cheapInput = document.getElementById('sim-cheap');
            const capableInput = document.getElementById('sim-capable');
            const premiumInput = document.getElementById('sim-premium');

            if (cheapVal && cheapInput) cheapVal.textContent = cheapInput.value + '%';
            if (capableVal && capableInput) capableVal.textContent = capableInput.value + '%';
            if (premiumVal && premiumInput) premiumVal.textContent = premiumInput.value + '%';
        }

        function runSimulator() {
            const providerSelect = document.getElementById('sim-provider');
            const scenarioSelect = document.getElementById('sim-scenario');
            const cheapInput = document.getElementById('sim-cheap');
            const capableInput = document.getElementById('sim-capable');
            const premiumInput = document.getElementById('sim-premium');
            const mixWarning = document.getElementById('sim-mix-warning');

            if (!providerSelect || !scenarioSelect || !cheapInput || !capableInput || !premiumInput) {
                return;
            }

            // Update slider labels first
            updateSliderLabels();

            const provider = providerSelect.value || 'cost-optimized';
            const scenario = scenarioSelect.value || 'default';

            const cheapPct = parseFloat(cheapInput.value) || 0;
            const capablePct = parseFloat(capableInput.value) || 0;
            const premiumPct = parseFloat(premiumInput.value) || 0;

            const sum = cheapPct + capablePct + premiumPct;
            if (mixWarning) {
                mixWarning.style.display = sum > 100.5 || sum < 99.5 ? 'block' : 'none';
            }

            const mix = normalizeMix(cheapPct, capablePct, premiumPct);
            const totalRequests = SIM_SCENARIOS[scenario] || SIM_SCENARIOS.default;

            const pricing = SIM_TIER_PRICING[provider] || SIM_TIER_PRICING['cost-optimized'];

            const cheapReq = totalRequests * mix.cheap;
            const capableReq = totalRequests * mix.capable;
            const premiumReq = totalRequests * mix.premium;

            const cheapCost = cheapReq * pricing.cheap;
            const capableCost = capableReq * pricing.capable;
            const premiumCost = premiumReq * pricing.premium;

            const actualCost = cheapCost + capableCost + premiumCost;

            // Baseline: all-premium at same total requests with provider's premium pricing
            const baselineCost = totalRequests * pricing.premium;
            const savings = baselineCost - actualCost;

            // Update summary
            const actualEl = document.getElementById('sim-actual');
            const baselineEl = document.getElementById('sim-baseline');
            const savingsEl = document.getElementById('sim-savings');

            if (actualEl) actualEl.textContent = '$' + actualCost.toFixed(2);
            if (baselineEl) baselineEl.textContent = '$' + baselineCost.toFixed(2);
            if (savingsEl) savingsEl.textContent = '$' + Math.max(0, savings).toFixed(2);

            // Update projection chart (monthly = 4 weeks)
            const monthlyActual = actualCost * 4;
            const monthlyBaseline = baselineCost * 4;
            const projectionChart = document.getElementById('sim-projection-chart');
            if (projectionChart && monthlyBaseline > 0) {
                const actualHeight = Math.max((monthlyActual / monthlyBaseline) * 100, 5);
                projectionChart.innerHTML =
                    '<div style="flex: 1; display: flex; flex-direction: column; align-items: center;">' +
                        '<div style="flex: 1; width: 100%; display: flex; align-items: flex-end;">' +
                            '<div style="width: 100%; height: ' + actualHeight + '%; background: linear-gradient(to top, var(--vscode-charts-green), var(--vscode-charts-blue)); border-radius: 2px;"></div>' +
                        '</div>' +
                        '<div style="font-size: 9px; margin-top: 2px;">$' + monthlyActual.toFixed(0) + '/mo</div>' +
                    '</div>' +
                    '<div style="flex: 1; display: flex; flex-direction: column; align-items: center;">' +
                        '<div style="flex: 1; width: 100%; display: flex; align-items: flex-end;">' +
                            '<div style="width: 100%; height: 100%; background: var(--vscode-input-background); border: 1px dashed var(--vscode-charts-red); border-radius: 2px; opacity: 0.6;"></div>' +
                        '</div>' +
                        '<div style="font-size: 9px; margin-top: 2px;">$' + monthlyBaseline.toFixed(0) + '/mo</div>' +
                    '</div>';
            }

            // Tier breakdown
            const tierEl = document.getElementById('sim-tier-breakdown');
            if (tierEl) {
                tierEl.innerHTML = [
                    { key: 'cheap', label: 'Cheap', req: cheapReq, cost: cheapCost, color: '#22c55e' },
                    { key: 'capable', label: 'Capable', req: capableReq, cost: capableCost, color: '#3b82f6' },
                    { key: 'premium', label: 'Premium', req: premiumReq, cost: premiumCost, color: '#a855f7' }
                ].map(t => {
                    return '<div style="padding: 4px 6px; border: 1px solid var(--border); border-radius: 3px;">' +
                        '<div style="display: flex; justify-content: space-between; align-items: center;">' +
                            '<span style="color: ' + t.color + '; font-weight: 600;">' + t.label + '</span>' +
                            '<span style="opacity: 0.7;">' + Math.round((t.req || 0)) + ' req</span>' +
                        '</div>' +
                        '<div style="font-size: 10px; opacity: 0.8; margin-top: 2px;">$' + (t.cost || 0).toFixed(2) + '</div>' +
                    '</div>';
                }).join('');
            }
        }

        // Real-time slider updates
        ['sim-cheap', 'sim-capable', 'sim-premium'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                // 'input' fires while dragging, 'change' fires on release
                el.addEventListener('input', function() {
                    runSimulator();
                });
            }
        });

        // Dropdown changes
        ['sim-provider', 'sim-scenario'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', function() {
                    runSimulator();
                });
            }
        });

        // Run once on initial load
        setTimeout(runSimulator, 0);

        function updateCosts(costs, isEmpty) {
            // Costs are now displayed in the dedicated Costs Panel
            // This function kept for potential future use
        }

        function showErrorBanner(errors) {
            const banner = document.getElementById('error-banner');
            if (!banner) return;

            if (!errors || Object.keys(errors).length === 0) {
                banner.style.display = 'none';
                return;
            }

            banner.innerHTML = Object.entries(errors)
                .map(([key, msg]) => '<div class="error-item">&#x26A0; ' + key + ': ' + msg + '</div>')
                .join('');
            banner.style.display = 'block';
        }

        // Panel navigation functions
        function openHealthPanel() {
            vscode.postMessage({ type: 'openHealthPanel' });
        }

        function openCostsPanel() {
            vscode.postMessage({ type: 'openCostsPanel' });
        }

        function openWorkflowHistory() {
            vscode.postMessage({ type: 'openWorkflowHistory' });
        }

        // Request initial data
        vscode.postMessage({ type: 'refresh' });
    </script>
</body>
</html>`;
    }

    public dispose() {
        if (this._fileWatcher) {
            this._fileWatcher.dispose();
        }
    }
}

interface PatternData {
    id: string;
    type: string;
    status: string;
    rootCause: string;
    fix: string;
    files: string[];
    timestamp: string;
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

interface CostData {
    totalCost: number;
    totalSavings: number;
    savingsPercent: number;
    requests: number;
    baselineCost: number;
    dailyCosts: Array<{ date: string; cost: number; savings: number }>;
    byProvider: Record<string, { requests: number; cost: number }>;
    // 7-day breakdown of requests and savings by tier (cheap/capable/premium)
    byTier?: Record<string, { requests: number; savings: number; cost: number }>;
}

// Response shape from `python -m empathy_os.models.cli telemetry --costs -f json`
interface TelemetryCostData {
    workflow_count: number;
    total_actual_cost: number;
    total_baseline_cost: number;
    total_savings: number;
    savings_percent: number;
    avg_cost_per_workflow: number;
}

// XML-enhanced finding from parsed response
interface XmlFinding {
    severity: string;
    title: string;
    location: string | null;
    details: string;
    fix: string;
}

// Workflow run that may include XML-parsed data
interface WorkflowRunData {
    workflow: string;
    success: boolean;
    cost: number;
    savings: number;
    timestamp: string;
    // XML-enhanced fields (optional)
    xml_parsed?: boolean;
    summary?: string;
    findings?: XmlFinding[];
    checklist?: string[];
}

interface WorkflowData {
    totalRuns: number;
    successfulRuns: number;
    totalCost: number;
    totalSavings: number;
    recentRuns: WorkflowRunData[];
    byWorkflow: Record<string, { runs: number; cost: number; savings: number }>;
}

function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
