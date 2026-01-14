'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  CostTrendChart,
  TierUsageChart,
  WorkflowPieChart,
  SavingsBarChart,
} from '../charts';

interface WorkflowRun {
  workflow: string;
  provider: string;
  success: boolean;
  started_at: string;
  savings_percent: number;
  cost: number;
  duration_ms: number;
  error?: string;
  tier?: 'cheap' | 'capable' | 'premium';
}

interface TimeSeriesData {
  date: string;
  cost: number;
  savings: number;
  baseline: number;
  cheap: number;
  capable: number;
  premium: number;
}

interface WorkflowComparisonData {
  name: string;
  runs: number;
  cost: number;
  savings: number;
  baseline: number;
  savingsPercent: number;
}

interface WorkflowStats {
  total_runs: number;
  successful_runs: number;
  by_workflow: Record<string, {
    runs: number;
    cost: number;
    savings: number;
    success: number;
  }>;
  by_provider: Record<string, {
    runs: number;
    cost: number;
  }>;
  by_tier: {
    cheap: number;
    capable: number;
    premium: number;
  };
  recent_runs: WorkflowRun[];
  total_cost: number;
  total_savings: number;
  avg_savings_percent: number;
  available_workflows: Array<{
    name: string;
    description: string;
    stages: string[];
    tier_map: Record<string, string>;
  }>;
  chart_data?: {
    time_series: TimeSeriesData[];
    workflow_comparison: WorkflowComparisonData[];
  };
}

// Helper to format relative time (e.g., "2 min ago", "1 hour ago")
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHour < 24) return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`;
  if (diffDay === 1) return 'yesterday';
  if (diffDay < 7) return `${diffDay} days ago`;
  return dateString.slice(0, 10);
}

export default function WorkflowDashboard() {
  const [stats, setStats] = useState<WorkflowStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`/api/workflows?days=${days}`);
      if (!res.ok) throw new Error('Failed to fetch');
      const data = await res.json();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetchStats();
    // Auto-refresh every 60 seconds (reduced from 30s to lower API load)
    const interval = setInterval(fetchStats, 60000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        Error: {error}
      </div>
    );
  }

  if (!stats) return null;

  const hasChartData = stats.chart_data &&
    stats.chart_data.time_series &&
    stats.chart_data.time_series.length > 0;

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Workflow Runs"
          value={stats.total_runs}
          label={`${stats.avg_savings_percent.toFixed(0)}% avg savings`}
        />
        <StatCard
          title="Success Rate"
          value={`${stats.total_runs > 0 ? ((stats.successful_runs / stats.total_runs) * 100).toFixed(0) : 0}%`}
          label={`${stats.successful_runs} successful`}
          variant="success"
        />
        <StatCard
          title="Total Cost"
          value={`$${stats.total_cost.toFixed(4)}`}
          label="across all runs"
        />
        <StatCard
          title="Total Savings"
          value={`$${stats.total_savings.toFixed(4)}`}
          label="vs premium baseline"
          variant="success"
        />
      </div>

      {/* Cost Trend Chart */}
      {hasChartData && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Cost Trends</h2>
            <div className="flex gap-2">
              {[7, 30, 90].map((d) => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className={`px-3 py-1 text-sm rounded-md transition-colors ${
                    days === d
                      ? 'bg-indigo-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {d}d
                </button>
              ))}
            </div>
          </div>
          <CostTrendChart data={stats.chart_data!.time_series} />
        </div>
      )}

      {/* Charts Row: Tier Usage & Workflow Distribution */}
      {hasChartData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Tier Usage Chart */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Model Tier Usage Over Time</h2>
            <TierUsageChart data={stats.chart_data!.time_series} />
          </div>

          {/* Workflow Distribution Pie Chart */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Workflow Distribution</h2>
            <WorkflowPieChart data={stats.chart_data!.workflow_comparison} />
          </div>
        </div>
      )}

      {/* Savings Comparison Bar Chart */}
      {hasChartData && stats.chart_data!.workflow_comparison.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Savings by Workflow</h2>
          <SavingsBarChart data={stats.chart_data!.workflow_comparison} />
        </div>
      )}

      {/* Workflows Grid */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Available Workflows</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {stats.available_workflows.map((wf) => {
            const wfStats = stats.by_workflow[wf.name];
            return (
              <div key={wf.name} className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-medium text-gray-900 mb-1">{wf.name}</h3>
                <p className="text-sm text-gray-500 mb-3">{wf.description}</p>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-indigo-600 font-semibold">
                    {wfStats?.runs || 0} runs
                  </span>
                  {wfStats && (
                    <span className="text-green-600">
                      ${wfStats.savings.toFixed(4)} saved
                    </span>
                  )}
                </div>
                <div className="mt-2 flex gap-1">
                  {wf.stages.map((stage) => (
                    <span
                      key={stage}
                      className={`text-xs px-2 py-0.5 rounded ${
                        wf.tier_map[stage] === 'cheap'
                          ? 'bg-green-100 text-green-700'
                          : wf.tier_map[stage] === 'capable'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-purple-100 text-purple-700'
                      }`}
                    >
                      {stage}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tier Usage Summary (Fallback when no chart data) */}
      {!hasChartData && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Model Tier Usage</h2>
          <TierUsageFallback byTier={stats.by_tier} />
        </div>
      )}

      {/* Recent Runs */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Runs</h2>
          <span className="text-xs text-gray-400">Auto-refresh: 60s</span>
        </div>
        {stats.recent_runs.length > 0 ? (
          <div className="space-y-2">
            {stats.recent_runs.slice(0, 5).map((run, idx) => (
              <div
                key={idx}
                className={`rounded-lg border p-3 ${
                  run.success
                    ? 'border-gray-100 bg-white'
                    : 'border-red-100 bg-red-50'
                }`}
              >
                <div className="flex items-center gap-3">
                  {/* Status icon */}
                  <span className={`text-lg ${run.success ? 'text-emerald-500' : 'text-red-500'}`}>
                    {run.success ? '✓' : '✗'}
                  </span>

                  {/* Workflow name */}
                  <span className="font-medium text-gray-900 min-w-[100px]">
                    {run.workflow}
                  </span>

                  {/* Duration badge */}
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded font-mono">
                    {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '--'}
                  </span>

                  {/* Cost badge */}
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded font-mono">
                    ${run.cost?.toFixed(4) || '0.00'}
                  </span>

                  {/* Tier badge with standardized colors */}
                  {run.tier && (
                    <span className={`text-xs px-2 py-1 rounded font-medium ${
                      run.tier === 'cheap'
                        ? 'bg-green-100 text-green-700'
                        : run.tier === 'capable'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-violet-100 text-violet-700'
                    }`}>
                      {run.tier}
                    </span>
                  )}

                  {/* Spacer */}
                  <span className="flex-1" />

                  {/* Savings (only show if successful) */}
                  {run.success && run.savings_percent > 0 && (
                    <span className="text-emerald-600 font-medium text-sm">
                      {run.savings_percent.toFixed(0)}% saved
                    </span>
                  )}

                  {/* Timestamp */}
                  <span className="text-gray-400 text-xs">
                    {run.started_at ? formatRelativeTime(run.started_at) : '--'}
                  </span>
                </div>

                {/* Error message (if failed) */}
                {!run.success && run.error && (
                  <div className="mt-2 pl-8">
                    <p className="text-xs text-red-600 font-mono bg-red-100 px-2 py-1 rounded inline-block">
                      {run.error.length > 80 ? `${run.error.slice(0, 80)}...` : run.error}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-gray-500 mb-4">
              No workflow runs yet. Get started with:
            </p>
            <div className="inline-flex flex-col gap-2">
              <code className="bg-gray-100 px-4 py-2 rounded text-sm font-mono text-indigo-600">
                empathy workflow run health-check --path .
              </code>
              <code className="bg-gray-100 px-4 py-2 rounded text-sm font-mono text-indigo-600">
                empathy workflow run release-prep --path .
              </code>
            </div>
          </div>
        )}
      </div>

      {/* CLI Commands */}
      <div className="bg-gray-50 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">CLI Commands</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <CommandCard cmd="empathy workflow list" desc="List all workflows" />
          <CommandCard cmd="empathy workflow run health-check --path ." desc="Run health check crew (v4.0.2)" isNew />
          <CommandCard cmd="empathy workflow run release-prep --path ." desc="Run release prep crew (v4.0.2)" isNew />
          <CommandCard cmd="empathy workflow run test-coverage-boost --path ." desc="Run test coverage crew (v4.0.2)" isNew />
          <CommandCard cmd="empathy workflow run code-review" desc="Run code review" />
          <CommandCard cmd="empathy workflow describe health-check" desc="View workflow details" />
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  label,
  variant = 'default',
}: {
  title: string;
  value: string | number;
  label: string;
  variant?: 'default' | 'success' | 'warning';
}) {
  const valueColor = {
    default: 'text-gray-900',
    success: 'text-green-600',
    warning: 'text-amber-600',
  }[variant];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
        {title}
      </h3>
      <p className={`mt-2 text-3xl font-bold ${valueColor}`}>{value}</p>
      <p className="mt-1 text-sm text-gray-500">{label}</p>
    </div>
  );
}

function TierUsageFallback({ byTier }: { byTier: { cheap: number; capable: number; premium: number } }) {
  const tierTotal = byTier.cheap + byTier.capable + byTier.premium;

  if (tierTotal === 0) {
    return <p className="text-gray-500">No tier data yet. Run a workflow to see usage.</p>;
  }

  return (
    <>
      <div className="h-6 rounded-lg overflow-hidden flex">
        <div
          className="bg-green-500 flex items-center justify-center text-white text-xs font-medium"
          style={{ width: `${(byTier.cheap / tierTotal) * 100}%` }}
        >
          {((byTier.cheap / tierTotal) * 100).toFixed(0)}%
        </div>
        <div
          className="bg-blue-500 flex items-center justify-center text-white text-xs font-medium"
          style={{ width: `${(byTier.capable / tierTotal) * 100}%` }}
        >
          {((byTier.capable / tierTotal) * 100).toFixed(0)}%
        </div>
        <div
          className="bg-purple-500 flex items-center justify-center text-white text-xs font-medium"
          style={{ width: `${(byTier.premium / tierTotal) * 100}%` }}
        >
          {((byTier.premium / tierTotal) * 100).toFixed(0)}%
        </div>
      </div>
      <div className="mt-3 flex gap-6 text-sm text-gray-600">
        <span className="flex items-center gap-2">
          <span className="w-3 h-3 bg-green-500 rounded"></span>
          Cheap: ${byTier.cheap.toFixed(4)}
        </span>
        <span className="flex items-center gap-2">
          <span className="w-3 h-3 bg-blue-500 rounded"></span>
          Capable: ${byTier.capable.toFixed(4)}
        </span>
        <span className="flex items-center gap-2">
          <span className="w-3 h-3 bg-purple-500 rounded"></span>
          Premium: ${byTier.premium.toFixed(4)}
        </span>
      </div>
    </>
  );
}

function CommandCard({ cmd, desc, isNew }: { cmd: string; desc: string; isNew?: boolean }) {
  return (
    <div className={`bg-white rounded-lg px-4 py-3 border ${isNew ? 'border-indigo-200 bg-indigo-50' : 'border-gray-200'}`}>
      <div className="flex items-center gap-2">
        <code className="text-sm text-indigo-600 font-mono flex-1">{cmd}</code>
        {isNew && (
          <span className="text-xs bg-indigo-600 text-white px-1.5 py-0.5 rounded font-medium">NEW</span>
        )}
      </div>
      <p className="text-xs text-gray-500 mt-1">{desc}</p>
    </div>
  );
}
