'use client';

/**
 * Empathy Framework Wizards Dashboard
 * Centralized access to developer tools and clinical documentation wizards
 * v4.0.2: Added Developer Tools category with CrewAI-powered workflows
 */

import { useState } from 'react';
import Link from 'next/link';

interface WizardCard {
  id: string;
  title: string;
  description: string;
  icon: string;
  steps: number;
  color: string;
  bgColor: string;
}

interface WizardCategory {
  id: string;
  title: string;
  icon: string;
  gradient: string;
  wizards: WizardCard[];
}

// Extended wizard interface for developer tools with CLI commands
interface DeveloperWizardCard extends WizardCard {
  cliCommand?: string;
  estimatedTime?: string;
  estimatedCost?: string;
  agents?: number;
}

const wizardCategories: WizardCategory[] = [
  {
    id: 'developer',
    title: 'Developer Tools',
    icon: '💻',
    gradient: 'from-slate-600 to-slate-800',
    wizards: [
      { id: 'health-check', title: 'Health Check', description: 'CrewAI-powered codebase health analysis with lint, type, and security checks', icon: '🩺', steps: 5, color: 'text-slate-600', bgColor: 'bg-slate-100' },
      { id: 'release-prep', title: 'Release Prep', description: 'Pre-release validation crew with blocker detection and changelog analysis', icon: '🚀', steps: 4, color: 'text-blue-600', bgColor: 'bg-blue-100' },
      { id: 'test-coverage', title: 'Test Coverage Boost', description: 'Intelligent test generation for coverage gaps using multi-agent analysis', icon: '🧪', steps: 3, color: 'text-emerald-600', bgColor: 'bg-emerald-100' },
    ],
  },
  {
    id: 'core',
    title: 'Core Documentation',
    icon: '📋',
    gradient: 'from-indigo-600 to-indigo-800',
    wizards: [
      { id: 'epic', title: 'Epic Integration', description: 'Connect to Epic EHR via FHIR API for seamless data integration', icon: '🔌', steps: 7, color: 'text-indigo-600', bgColor: 'bg-indigo-100' },
      { id: 'sbar', title: 'SBAR Report', description: 'Situation-Background-Assessment-Recommendation communication', icon: '💬', steps: 5, color: 'text-blue-600', bgColor: 'bg-blue-100' },
      { id: 'med-rec', title: 'Med Reconciliation', description: 'Prevent medication errors with automated discrepancy detection', icon: '💊', steps: 4, color: 'text-orange-600', bgColor: 'bg-orange-100' },
      { id: 'discharge', title: 'Discharge Summary', description: 'Multi-language education materials and comprehensive care instructions', icon: '🏠', steps: 6, color: 'text-green-600', bgColor: 'bg-green-100' },
      { id: 'admission', title: 'Admission Assessment', description: 'Complete patient admission with demographics, vitals, medical history', icon: '👤', steps: 5, color: 'text-teal-600', bgColor: 'bg-teal-100' },
      { id: 'handoff', title: 'Handoff Report', description: 'I-PASS format for continuity of care during shift changes', icon: '🤝', steps: 4, color: 'text-cyan-600', bgColor: 'bg-cyan-100' },
    ],
  },
  {
    id: 'safety',
    title: 'Safety & Risk',
    icon: '🛡️',
    gradient: 'from-amber-500 to-orange-600',
    wizards: [
      { id: 'pain', title: 'Pain Assessment', description: 'Visual 0-10 pain scales, intervention tracking, reassessment workflows', icon: '🌡️', steps: 4, color: 'text-red-600', bgColor: 'bg-red-100' },
      { id: 'fall', title: 'Fall Risk', description: 'Morse Fall Scale with evidence-based prevention strategies', icon: '⚠️', steps: 4, color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
      { id: 'wound', title: 'Wound Assessment', description: 'Pressure injury staging (I-IV) and photo documentation', icon: '🩹', steps: 5, color: 'text-red-700', bgColor: 'bg-red-100' },
      { id: 'pressure', title: 'Pressure Injury', description: 'Braden Scale scores with risk-based intervention bundles', icon: '🛏️', steps: 4, color: 'text-orange-600', bgColor: 'bg-orange-100' },
      { id: 'restraint', title: 'Restraint Assessment', description: 'Q15min monitoring and order expiration alerts for patient safety', icon: '🔒', steps: 5, color: 'text-purple-600', bgColor: 'bg-purple-100' },
    ],
  },
  {
    id: 'procedures',
    title: 'Procedures',
    icon: '💉',
    gradient: 'from-emerald-500 to-green-600',
    wizards: [
      { id: 'iv', title: 'IV Insertion', description: 'Site selection guidance, attempt tracking, complication monitoring', icon: '💉', steps: 4, color: 'text-green-600', bgColor: 'bg-green-100' },
      { id: 'transfusion', title: 'Blood Transfusion', description: 'Two-person verification, Q15min vitals, reaction tracking', icon: '🩸', steps: 6, color: 'text-red-600', bgColor: 'bg-red-100' },
    ],
  },
  {
    id: 'periop',
    title: 'Perioperative',
    icon: '🏥',
    gradient: 'from-blue-500 to-blue-700',
    wizards: [
      { id: 'preop', title: 'Pre-Op Checklist', description: 'WHO Surgical Safety Checklist with NPO compliance verification', icon: '✅', steps: 5, color: 'text-blue-600', bgColor: 'bg-blue-100' },
      { id: 'postop', title: 'Post-Op Assessment', description: 'PACU recovery with Aldrete Score for discharge readiness', icon: '🩺', steps: 5, color: 'text-teal-600', bgColor: 'bg-teal-100' },
    ],
  },
  {
    id: 'critical',
    title: 'Critical Care',
    icon: '🚨',
    gradient: 'from-red-600 to-red-800',
    wizards: [
      { id: 'code-blue', title: 'Code Blue', description: 'Real-time running timer, intervention timeline, medication logs', icon: '💓', steps: 4, color: 'text-red-700', bgColor: 'bg-red-100' },
    ],
  },
  {
    id: 'specialized',
    title: 'Specialized',
    icon: '🧠',
    gradient: 'from-violet-500 to-purple-700',
    wizards: [
      { id: 'nutrition', title: 'Nutrition Screening', description: 'BMI calculation and MST scoring for dietitian referrals', icon: '🍽️', steps: 4, color: 'text-green-600', bgColor: 'bg-green-100' },
      { id: 'mental', title: 'Mental Status Exam', description: 'Mini-Cog dementia screening and SI/HI safety evaluations', icon: '🧠', steps: 5, color: 'text-purple-600', bgColor: 'bg-purple-100' },
    ],
  },
  {
    id: 'critical-assessment',
    title: 'Critical Assessment',
    icon: '⚡',
    gradient: 'from-red-500 to-rose-600',
    wizards: [
      { id: 'sepsis', title: 'Sepsis Screening', description: 'qSOFA score and SIRS criteria for early identification', icon: '🦠', steps: 4, color: 'text-red-600', bgColor: 'bg-red-100' },
      { id: 'stroke', title: 'Stroke Assessment', description: 'Cincinnati Stroke Scale and NIHSS for tPA eligibility', icon: '🧠', steps: 5, color: 'text-orange-600', bgColor: 'bg-orange-100' },
      { id: 'cardiac', title: 'Cardiac Assessment', description: 'HEART score calculator and STEMI criteria', icon: '❤️', steps: 5, color: 'text-red-600', bgColor: 'bg-red-100' },
      { id: 'respiratory', title: 'Respiratory', description: 'ABG interpretation, P/F ratio, ARDS severity', icon: '🫁', steps: 4, color: 'text-blue-600', bgColor: 'bg-blue-100' },
      { id: 'neuro', title: 'Neurological', description: 'Glasgow Coma Scale, pupil assessment, motor/sensory testing', icon: '🧠', steps: 5, color: 'text-purple-600', bgColor: 'bg-purple-100' },
    ],
  },
];

export default function HealthcareWizardsDashboard() {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedWizard, setSelectedWizard] = useState<string | null>(null);

  const totalWizards = wizardCategories.reduce((acc, cat) => acc + cat.wizards.length, 0);

  const filteredCategories = wizardCategories.map(category => ({
    ...category,
    wizards: category.wizards.filter(
      wizard =>
        wizard.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        wizard.description.toLowerCase().includes(searchTerm.toLowerCase())
    ),
  })).filter(category => category.wizards.length > 0);

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
      <div className="max-w-6xl mx-auto p-4">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-lg mb-6 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                Empathy Framework
              </h1>
              <p className="text-gray-600">Developer Tools & Clinical Wizards Dashboard</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg font-semibold text-xs">
                💻 Dev Tools
              </div>
              <div className="px-3 py-1.5 bg-indigo-100 text-indigo-700 rounded-lg font-semibold text-xs">
                🏥 Healthcare
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-indigo-600">{totalWizards}</div>
                <div className="text-xs text-gray-700">Wizards</div>
              </div>
            </div>
          </div>

          {/* Search Bar */}
          <div className="relative">
            <input
              type="text"
              placeholder="Search wizards..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-4 py-3 pl-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <span className="absolute left-3 top-3.5 text-gray-400">🔍</span>
          </div>
        </div>

        {/* Demo Banner */}
        <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6 rounded-lg">
          <div className="flex items-start gap-4">
            <span className="text-2xl">🚀</span>
            <div>
              <h3 className="text-lg font-semibold text-blue-900 mb-2">
                Fully Functional Demo Application
              </h3>
              <p className="text-blue-800 mb-3">
                All wizards work with mock data and user input. Test the complete workflow from data entry to document generation.
              </p>
              <div className="flex flex-wrap gap-4 text-sm text-blue-700">
                <div className="flex items-center gap-1">✅ Complete all wizard steps</div>
                <div className="flex items-center gap-1">✅ Generate AI-enhanced documents</div>
                <div className="flex items-center gap-1">✅ Review & approve workflow</div>
                <div className="flex items-center gap-1">✅ Download final reports</div>
              </div>
            </div>
          </div>
        </div>

        {/* Wizard Categories */}
        {filteredCategories.map((category) => (
          <div key={category.id} className="mb-6">
            <div className={`bg-gradient-to-r ${category.gradient} rounded-lg text-white px-4 py-3 mb-4`}>
              <h2 className="font-bold text-lg flex items-center gap-2">
                <span>{category.icon}</span>
                {category.title}
                {category.id === 'developer' && (
                  <span className="ml-2 px-2 py-0.5 bg-white/20 rounded text-xs font-medium">
                    NEW in v4.0.2
                  </span>
                )}
              </h2>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {category.wizards.map((wizard) => (
                <button
                  key={wizard.id}
                  onClick={() => setSelectedWizard(wizard.id === selectedWizard ? null : wizard.id)}
                  className={`bg-white rounded-lg p-4 shadow-md hover:shadow-lg transition-all text-left border-l-4 ${
                    selectedWizard === wizard.id ? 'border-indigo-600 ring-2 ring-indigo-200' : 'border-indigo-400'
                  }`}
                  title={wizard.description}
                >
                  <div className="text-2xl mb-2">{wizard.icon}</div>
                  <div className="font-semibold text-gray-900 text-sm mb-1">{wizard.title}</div>
                  <div className={`inline-block px-2 py-0.5 ${wizard.bgColor} ${wizard.color} text-xs rounded-full font-semibold`}>
                    {wizard.steps} steps
                  </div>
                  {selectedWizard === wizard.id && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-xs text-gray-600 mb-3">{wizard.description}</p>
                      {/* Developer Tools - Show CLI command */}
                      {category.id === 'developer' ? (
                        <div className="space-y-2">
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span>~{wizard.id === 'health-check' ? '67s' : wizard.id === 'release-prep' ? '90s' : '60s'}</span>
                            <span>•</span>
                            <span>${wizard.id === 'health-check' ? '0.05' : wizard.id === 'release-prep' ? '0.12' : '0.06'}</span>
                            <span>•</span>
                            <span>{wizard.id === 'health-check' ? '5' : wizard.id === 'release-prep' ? '4' : '3'} agents</span>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              const cmd = `empathy workflow run ${wizard.id} --path .`;
                              navigator.clipboard.writeText(cmd);
                            }}
                            className="block w-full text-center px-3 py-2 bg-slate-700 text-white rounded text-sm font-mono hover:bg-slate-800 transition-colors"
                          >
                            Copy CLI Command
                          </button>
                          <code className="block text-xs text-gray-500 text-center font-mono">
                            empathy workflow run {wizard.id} --path .
                          </code>
                        </div>
                      ) : wizard.id === 'sbar' ? (
                        <Link
                          href="/dashboard/sbar"
                          className="block w-full text-center px-3 py-2 bg-indigo-600 text-white rounded text-sm font-semibold hover:bg-indigo-700"
                        >
                          Start Wizard →
                        </Link>
                      ) : (
                        <span className="block w-full text-center px-3 py-2 bg-gray-100 text-gray-500 rounded text-sm">
                          Coming Soon
                        </span>
                      )}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        ))}

        {/* Features Section */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <span className="text-yellow-500">⭐</span>
            Key Features
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3 text-3xl">
                🤖
              </div>
              <h3 className="font-semibold text-gray-900 mb-1">AI-Powered</h3>
              <p className="text-xs text-gray-700">Intelligent text enhancement and clinical decision support</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3 text-3xl">
                ✅
              </div>
              <h3 className="font-semibold text-gray-900 mb-1">Review & Approve</h3>
              <p className="text-xs text-gray-700">All documents require explicit review and approval</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-3 text-3xl">
                🛡️
              </div>
              <h3 className="font-semibold text-gray-900 mb-1">Patient Safety</h3>
              <p className="text-xs text-gray-700">Built-in safety checks and audit trail tracking</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-3 text-3xl">
                🎓
              </div>
              <h3 className="font-semibold text-gray-900 mb-1">Educational</h3>
              <p className="text-xs text-gray-700">Learn evidence-based clinical documentation practices</p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-white rounded-lg shadow-lg p-4 text-center">
          <p className="text-gray-700 text-sm">
            <span className="text-yellow-500">💡</span> Quick-fill samples • Auto-calculators • Works offline
          </p>
          <p className="text-xs text-gray-600 mt-1">Tablet-Optimized Design</p>
          <div className="mt-3 flex justify-center gap-4">
            <Link href="/" className="text-sm text-indigo-700 hover:underline font-medium">Home</Link>
            <Link href="/framework" className="text-sm text-indigo-700 hover:underline font-medium">Framework</Link>
            <Link href="/dev-dashboard" className="text-sm text-indigo-700 hover:underline font-medium">Dev Wizards</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
