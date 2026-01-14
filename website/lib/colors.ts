/**
 * Empathy Framework - Shared Color Constants
 * v4.0.2: Standardized tier and status colors across all UIs
 *
 * Use these constants for consistent styling across:
 * - Website dashboard
 * - Workflow dashboard
 * - VS Code extension (reference these hex values)
 */

// =============================================================================
// TIER COLORS - Model tier indicators (cheap, capable, premium)
// =============================================================================

export const TIER_COLORS = {
  cheap: {
    bg: 'bg-green-100',
    text: 'text-green-700',
    border: 'border-green-200',
    hex: '#22c55e', // green-500
    hexLight: '#dcfce7', // green-100
  },
  capable: {
    bg: 'bg-blue-100',
    text: 'text-blue-700',
    border: 'border-blue-200',
    hex: '#3b82f6', // blue-500
    hexLight: '#dbeafe', // blue-100
  },
  premium: {
    bg: 'bg-violet-100',
    text: 'text-violet-700',
    border: 'border-violet-200',
    hex: '#8b5cf6', // violet-500
    hexLight: '#ede9fe', // violet-100
  },
} as const;

// =============================================================================
// STATUS COLORS - Workflow/task status indicators
// =============================================================================

export const STATUS_COLORS = {
  success: {
    bg: 'bg-emerald-100',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
    hex: '#10b981', // emerald-500
    hexLight: '#d1fae5', // emerald-100
  },
  error: {
    bg: 'bg-red-100',
    text: 'text-red-700',
    border: 'border-red-200',
    hex: '#ef4444', // red-500
    hexLight: '#fee2e2', // red-100
  },
  warning: {
    bg: 'bg-amber-100',
    text: 'text-amber-700',
    border: 'border-amber-200',
    hex: '#f59e0b', // amber-500
    hexLight: '#fef3c7', // amber-100
  },
  running: {
    bg: 'bg-indigo-100',
    text: 'text-indigo-700',
    border: 'border-indigo-200',
    hex: '#6366f1', // indigo-500
    hexLight: '#e0e7ff', // indigo-100
  },
  pending: {
    bg: 'bg-gray-100',
    text: 'text-gray-600',
    border: 'border-gray-200',
    hex: '#6b7280', // gray-500
    hexLight: '#f3f4f6', // gray-100
  },
} as const;

// =============================================================================
// HEALTH SCORE COLORS - Project health indicators
// =============================================================================

export const HEALTH_COLORS = {
  excellent: {
    // 90-100
    bg: 'bg-emerald-100',
    text: 'text-emerald-700',
    hex: '#10b981',
    label: 'Excellent',
  },
  good: {
    // 70-89
    bg: 'bg-green-100',
    text: 'text-green-700',
    hex: '#22c55e',
    label: 'Good',
  },
  needsAttention: {
    // 50-69
    bg: 'bg-amber-100',
    text: 'text-amber-700',
    hex: '#f59e0b',
    label: 'Needs Attention',
  },
  critical: {
    // 0-49
    bg: 'bg-red-100',
    text: 'text-red-700',
    hex: '#ef4444',
    label: 'Critical',
  },
} as const;

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

export function getTierColor(tier: 'cheap' | 'capable' | 'premium') {
  return TIER_COLORS[tier] || TIER_COLORS.capable;
}

export function getStatusColor(status: keyof typeof STATUS_COLORS) {
  return STATUS_COLORS[status] || STATUS_COLORS.pending;
}

export function getHealthColor(score: number) {
  if (score >= 90) return HEALTH_COLORS.excellent;
  if (score >= 70) return HEALTH_COLORS.good;
  if (score >= 50) return HEALTH_COLORS.needsAttention;
  return HEALTH_COLORS.critical;
}

// Type exports for TypeScript consumers
export type TierType = keyof typeof TIER_COLORS;
export type StatusType = keyof typeof STATUS_COLORS;
export type HealthLevel = keyof typeof HEALTH_COLORS;
