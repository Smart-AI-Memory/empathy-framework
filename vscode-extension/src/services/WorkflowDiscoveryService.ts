/**
 * Workflow Discovery Service
 *
 * Discovers available workflows from the Python CLI and caches results.
 * Provides auto-discovery at startup and on-demand refresh.
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';
import { promisify } from 'util';
import { Workflow, WorkflowCategory, PythonWorkflowData } from '../types/workflow';

const execFile = promisify(cp.execFile);

export class WorkflowDiscoveryService {
    private static readonly CACHE_KEY = 'empathy.discoveredWorkflows';
    private static readonly CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

    private context: vscode.ExtensionContext;
    private cachedWorkflows: Workflow[] | null = null;
    private cacheTimestamp: number | null = null;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
    }

    /**
     * Discover all workflows from Python CLI
     */
    async discoverWorkflows(forceRefresh = false): Promise<Workflow[]> {
        // Check cache first
        if (!forceRefresh && this.cachedWorkflows && this.isCacheFresh()) {
            return this.cachedWorkflows;
        }

        try {
            // Try to discover from Python CLI
            const workflows = await this.discoverFromPythonCLI();

            // Cache the results
            await this.cacheWorkflows(workflows);

            return workflows;
        } catch (error) {
            console.error('[WorkflowDiscovery] Failed to discover from Python CLI:', error);

            // Fall back to cached workflows if available
            const cached = await this.loadCachedWorkflows();
            if (cached.length > 0) {
                console.log('[WorkflowDiscovery] Using cached workflows');
                return cached;
            }

            // Fall back to built-in workflows
            console.log('[WorkflowDiscovery] Using built-in workflow list');
            return this.getBuiltInWorkflows();
        }
    }

    /**
     * Discover workflows from Python CLI
     */
    private async discoverFromPythonCLI(): Promise<Workflow[]> {
        const pythonPath = vscode.workspace.getConfiguration('empathy').get<string>('pythonPath') || 'python';
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

        if (!workspaceFolder) {
            throw new Error('No workspace folder found');
        }

        // v4.6.3: Run: empathy workflow list --json
        const { stdout } = await execFile('empathy', ['workflow', 'list', '--json'], {
            cwd: workspaceFolder,
            timeout: 10000,
        });

        const pythonWorkflows: PythonWorkflowData[] = JSON.parse(stdout);

        // Convert Python workflow data to our Workflow format
        const workflows = pythonWorkflows.map((wf: PythonWorkflowData) => ({
            name: wf.name,
            description: wf.description,
            category: this.categorizeWorkflow(wf.name),
            stages: wf.stages,
            icon: this.getIconForWorkflow(wf.name),
        }));

        return workflows;
    }

    /**
     * Categorize a workflow based on its name
     *
     * Categories:
     * - quick: Fast, commonly-used workflows for quick checks
     * - tool: Code generation and modification tools
     * - workflow: Complex multi-step analysis workflows
     * - view: Dashboard and reporting views (currently none)
     */
    private categorizeWorkflow(name: string): WorkflowCategory {
        // Quick category: Fast workflows for quick checks (< 30s typical)
        const quickWorkflows = [
            'health-check',     // Quick project health snapshot
            'bug-predict',      // Fast pattern-based bug detection
            'code-review',      // Quick code analysis
        ];
        if (quickWorkflows.includes(name)) {
            return 'quick';
        }

        // Tool category: Code generation and modification tools
        const toolWorkflows = [
            'doc-gen',          // Documentation generation
            'test-gen',         // Test generation
            'refactor-plan',    // Refactoring planner
            'manage-docs',      // Documentation management
            'keyboard-shortcuts', // Keyboard shortcut generation
        ];
        if (toolWorkflows.includes(name)) {
            return 'tool';
        }

        // View category: Dashboards and reports
        // (None currently - placeholder for future dashboard workflows)
        const viewWorkflows: string[] = [];
        if (viewWorkflows.includes(name)) {
            return 'view';
        }

        // Workflow category: Complex multi-step workflows
        // Includes: security-audit, perf-audit, dependency-check, release-prep,
        //           secure-release, pro-review, pr-review, doc-orchestrator
        return 'workflow';
    }

    /**
     * Get appropriate icon for a workflow based on its name
     */
    private getIconForWorkflow(name: string): string {
        const iconMap: Record<string, string> = {
            'morning': '$(calendar)',
            'ship': '$(rocket)',
            'fix-all': '$(tools)',
            'learn': '$(mortar-board)',
            'bug-predict': '$(bug)',
            'code-review': '$(eye)',
            'security-audit': '$(shield)',
            'perf-audit': '$(dashboard)',
            'test-gen': '$(beaker)',
            'doc-gen': '$(book)',
            'dashboard': '$(dashboard)',
            'costs': '$(graph)',
            'status': '$(info)',
            'refactor-plan': '$(wrench)',
            'release-prep': '$(package)',
            'health-check': '$(pulse)',
        };

        return iconMap[name] || '$(symbol-misc)';
    }

    /**
     * Get a specific workflow by name
     */
    async getWorkflow(name: string): Promise<Workflow | undefined> {
        const workflows = await this.discoverWorkflows();
        return workflows.find(w => w.name === name);
    }

    /**
     * Get workflows filtered by category
     */
    async getWorkflowsByCategory(category: WorkflowCategory): Promise<Workflow[]> {
        const workflows = await this.discoverWorkflows();
        return workflows.filter(w => w.category === category);
    }

    /**
     * Cache workflows to extension global state
     */
    private async cacheWorkflows(workflows: Workflow[]): Promise<void> {
        this.cachedWorkflows = workflows;
        this.cacheTimestamp = Date.now();

        await this.context.globalState.update(WorkflowDiscoveryService.CACHE_KEY, {
            workflows,
            timestamp: this.cacheTimestamp,
        });
    }

    /**
     * Load workflows from cache
     */
    private async loadCachedWorkflows(): Promise<Workflow[]> {
        const cached = this.context.globalState.get<{
            workflows: Workflow[];
            timestamp: number;
        }>(WorkflowDiscoveryService.CACHE_KEY);

        if (!cached) {
            return [];
        }

        this.cachedWorkflows = cached.workflows;
        this.cacheTimestamp = cached.timestamp;

        return cached.workflows;
    }

    /**
     * Check if cache is fresh (within TTL)
     */
    private isCacheFresh(): boolean {
        if (!this.cacheTimestamp) {
            return false;
        }

        const age = Date.now() - this.cacheTimestamp;
        return age < WorkflowDiscoveryService.CACHE_TTL_MS;
    }

    /**
     * Refresh workflows (force re-discovery)
     */
    async refreshWorkflows(): Promise<Workflow[]> {
        return this.discoverWorkflows(true);
    }

    /**
     * Get built-in workflows (fallback)
     */
    private getBuiltInWorkflows(): Workflow[] {
        return [
            // Quick category
            { name: 'morning', description: 'Morning briefing', category: 'quick', icon: '$(calendar)', isBuiltIn: true },
            { name: 'ship', description: 'Pre-ship check', category: 'quick', icon: '$(rocket)', isBuiltIn: true },
            { name: 'fix-all', description: 'Fix all issues', category: 'quick', icon: '$(tools)', isBuiltIn: true },
            { name: 'learn', description: 'Learn patterns', category: 'quick', icon: '$(mortar-board)', isBuiltIn: true },

            // Workflow category
            { name: 'bug-predict', description: 'Predict bugs from patterns', category: 'workflow', icon: '$(bug)', isBuiltIn: true },
            { name: 'code-review', description: 'Code review workflow', category: 'workflow', icon: '$(eye)', isBuiltIn: true },
            { name: 'security-audit', description: 'Security audit', category: 'workflow', icon: '$(shield)', isBuiltIn: true },
            { name: 'perf-audit', description: 'Performance audit', category: 'workflow', icon: '$(dashboard)', isBuiltIn: true },
            { name: 'test-gen', description: 'Generate tests', category: 'workflow', icon: '$(beaker)', isBuiltIn: true },
            { name: 'doc-gen', description: 'Generate documentation', category: 'workflow', icon: '$(book)', isBuiltIn: true },

            // View category
            { name: 'dashboard', description: 'Open dashboard', category: 'view', icon: '$(dashboard)', isBuiltIn: true },
            { name: 'costs', description: 'View API costs', category: 'view', icon: '$(graph)', isBuiltIn: true },
            { name: 'status', description: 'Show status', category: 'view', icon: '$(info)', isBuiltIn: true },
        ];
    }
}
