#!/usr/bin/env python3
"""Web dashboard for Empathy Framework Meta-Workflows.

Provides an attractive web interface for browsing templates, configuring
workflows, and viewing execution results.

Run with: python web_dashboard.py
Then open: http://localhost:8000
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from flask import Flask, jsonify, render_template_string

from empathy_os.meta_workflows import TemplateRegistry

app = Flask(__name__)

# Initialize template registry
templates_dir = Path(__file__).parent / ".empathy" / "meta_workflows" / "templates"
registry = TemplateRegistry(storage_dir=str(templates_dir))


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Empathy Framework - Meta-Workflows</title>
    <style>
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --bg: #f9fafb;
            --card-bg: #ffffff;
            --text: #111827;
            --text-muted: #6b7280;
            --border: #e5e7eb;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 2rem 0;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        header .container {
            padding: 0 2rem;
        }

        h1 {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        .subtitle {
            font-size: 1.1rem;
            opacity: 0.9;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: var(--card-bg);
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
        }

        .stat-label {
            color: var(--text-muted);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
        }

        .templates-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 1.5rem;
        }

        .template-card {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
            transition: all 0.3s ease;
            cursor: pointer;
        }

        .template-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
            border-color: var(--primary);
        }

        .template-header {
            display: flex;
            align-items: start;
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .template-icon {
            font-size: 2rem;
        }

        .template-title {
            flex: 1;
        }

        .template-name {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 0.25rem;
        }

        .template-id {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: monospace;
        }

        .template-description {
            color: var(--text-muted);
            margin-bottom: 1rem;
            line-height: 1.5;
        }

        .template-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }

        .meta-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            padding: 0.25rem 0.75rem;
            background: var(--bg);
            border-radius: 6px;
            font-size: 0.875rem;
            color: var(--text-muted);
        }

        .cost-range {
            background: linear-gradient(135deg, var(--success) 0%, var(--warning) 100%);
            color: white;
            font-weight: 600;
        }

        .template-actions {
            display: flex;
            gap: 0.75rem;
        }

        .btn {
            flex: 1;
            padding: 0.75rem 1rem;
            border: none;
            border-radius: 8px;
            font-size: 0.875rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: center;
            text-decoration: none;
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-dark);
        }

        .btn-secondary {
            background: var(--bg);
            color: var(--text);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: var(--border);
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }

        .modal.active {
            display: flex;
        }

        .modal-content {
            background: var(--card-bg);
            border-radius: 16px;
            max-width: 800px;
            max-height: 90vh;
            width: 100%;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }

        .modal-header {
            padding: 2rem;
            border-bottom: 1px solid var(--border);
        }

        .modal-title {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        .modal-body {
            padding: 2rem;
        }

        .question-group {
            margin-bottom: 2rem;
        }

        .question-label {
            font-weight: 600;
            margin-bottom: 0.5rem;
            display: block;
        }

        .question-help {
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
        }

        select, input[type="checkbox"] {
            padding: 0.75rem;
            border: 1px solid var(--border);
            border-radius: 8px;
            width: 100%;
            font-size: 1rem;
        }

        select:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }

        .checkbox-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .checkbox-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .checkbox-item input[type="checkbox"] {
            width: auto;
        }

        .modal-footer {
            padding: 1.5rem 2rem;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 1rem;
            justify-content: flex-end;
        }

        .close-btn {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: var(--text-muted);
            width: 2rem;
            height: 2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 4px;
        }

        .close-btn:hover {
            background: var(--bg);
        }

        .loading {
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-muted);
        }

        .spinner {
            display: inline-block;
            width: 3rem;
            height: 3rem;
            border: 4px solid var(--border);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>🧠 Empathy Framework</h1>
            <div class="subtitle">Meta-Workflow System - Intelligent Agent Orchestration</div>
        </div>
    </header>

    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Available Templates</div>
                <div class="stat-value" id="template-count">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Questions</div>
                <div class="stat-value" id="question-count">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Agents</div>
                <div class="stat-value" id="agent-count">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Cost Range</div>
                <div class="stat-value" id="cost-range">-</div>
            </div>
        </div>

        <div id="templates-container" class="templates-grid">
            <div class="loading">
                <div class="spinner"></div>
                <p>Loading templates...</p>
            </div>
        </div>
    </div>

    <div id="modal" class="modal">
        <div class="modal-content">
            <button class="close-btn" onclick="closeModal()">&times;</button>
            <div class="modal-header">
                <div class="modal-title" id="modal-title">Template Details</div>
                <div id="modal-subtitle" class="question-help"></div>
            </div>
            <div class="modal-body" id="modal-body">
                <!-- Dynamic content -->
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeModal()">Close</button>
                <button class="btn btn-primary" onclick="runWorkflow()">Run Workflow</button>
            </div>
        </div>
    </div>

    <script>
        let templates = [];
        let currentTemplate = null;

        // XSS Prevention: Escape HTML entities in user-facing content
        function escapeHtml(text) {
            if (text === null || text === undefined) return '';
            const div = document.createElement('div');
            div.textContent = String(text);
            return div.innerHTML;
        }

        async function loadTemplates() {
            try {
                const response = await fetch('/api/templates');
                templates = await response.json();
                renderTemplates();
                updateStats();
            } catch (error) {
                console.error('Failed to load templates:', error);
                document.getElementById('templates-container').innerHTML =
                    '<div class="loading"><p>Failed to load templates</p></div>';
            }
        }

        function updateStats() {
            const totalQuestions = templates.reduce((sum, t) => sum + t.questions, 0);
            const totalAgents = templates.reduce((sum, t) => sum + t.agents, 0);
            const minCost = Math.min(...templates.map(t => t.cost_min));
            const maxCost = Math.max(...templates.map(t => t.cost_max));

            document.getElementById('template-count').textContent = templates.length;
            document.getElementById('question-count').textContent = totalQuestions;
            document.getElementById('agent-count').textContent = totalAgents;
            document.getElementById('cost-range').textContent = `$${minCost.toFixed(2)}-$${maxCost.toFixed(2)}`;
        }

        function renderTemplates() {
            const container = document.getElementById('templates-container');
            const icons = {
                'python_package_publish': '📦',
                'code_refactoring_workflow': '🔧',
                'security_audit_workflow': '🔒',
                'documentation_generation_workflow': '📚',
                'test_creation_management_workflow': '🧪'
            };

            container.innerHTML = templates.map(template => `
                <div class="template-card" onclick="showTemplate('${escapeHtml(template.id)}')">
                    <div class="template-header">
                        <div class="template-icon">${icons[template.id] || '⚙️'}</div>
                        <div class="template-title">
                            <div class="template-name">${escapeHtml(template.name)}</div>
                            <div class="template-id">${escapeHtml(template.id)}</div>
                        </div>
                    </div>
                    <div class="template-description">${escapeHtml(template.description)}</div>
                    <div class="template-meta">
                        <span class="meta-badge">📋 ${template.questions} questions</span>
                        <span class="meta-badge">🤖 ${template.agents} agents</span>
                        <span class="meta-badge cost-range">💰 $${template.cost_min.toFixed(2)}-$${template.cost_max.toFixed(2)}</span>
                    </div>
                    <div class="template-actions">
                        <button class="btn btn-secondary" onclick="event.stopPropagation(); inspectTemplate('${escapeHtml(template.id)}')">Inspect</button>
                        <button class="btn btn-primary" onclick="event.stopPropagation(); runTemplate('${escapeHtml(template.id)}')">Run</button>
                    </div>
                </div>
            `).join('');
        }

        async function showTemplate(templateId) {
            const response = await fetch(`/api/templates/${templateId}`);
            const template = await response.json();
            currentTemplate = template;

            document.getElementById('modal-title').textContent = template.name;
            document.getElementById('modal-subtitle').textContent = template.description;

            const questionsHtml = template.form_schema.questions.map((q, i) => `
                <div class="question-group">
                    <label class="question-label">${i + 1}. ${escapeHtml(q.text)}</label>
                    ${q.help_text ? `<div class="question-help">${escapeHtml(q.help_text)}</div>` : ''}
                    ${renderQuestionInput(q)}
                </div>
            `).join('');

            document.getElementById('modal-body').innerHTML = questionsHtml;
            document.getElementById('modal').classList.add('active');
        }

        function renderQuestionInput(question) {
            const safeId = escapeHtml(question.id);
            if (question.type === 'single_select') {
                return `
                    <select id="q_${safeId}">
                        <option value="">-- Select --</option>
                        ${question.options.map(opt => `<option value="${escapeHtml(opt)}">${escapeHtml(opt)}</option>`).join('')}
                    </select>
                `;
            } else if (question.type === 'multi_select') {
                return `
                    <div class="checkbox-group">
                        ${question.options.map(opt => `
                            <label class="checkbox-item">
                                <input type="checkbox" name="q_${safeId}" value="${escapeHtml(opt)}">
                                ${escapeHtml(opt)}
                            </label>
                        `).join('')}
                    </div>
                `;
            } else if (question.type === 'boolean') {
                return `
                    <select id="q_${safeId}">
                        <option value="">-- Select --</option>
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                    </select>
                `;
            } else {
                return `<input type="text" id="q_${safeId}" placeholder="Enter value">`;
            }
        }

        function closeModal() {
            document.getElementById('modal').classList.remove('active');
        }

        async function inspectTemplate(templateId) {
            window.location.href = `/inspect/${templateId}`;
        }

        function runTemplate(templateId) {
            showTemplate(templateId);
        }

        function runWorkflow() {
            alert('Workflow execution will be implemented with real LLM integration in Phase 2');
        }

        // Load templates on page load
        loadTemplates();

        // Close modal on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
        });

        // Close modal on backdrop click
        document.getElementById('modal').addEventListener('click', (e) => {
            if (e.target.id === 'modal') closeModal();
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/templates')
def api_templates():
    """API endpoint to list all templates."""
    templates = registry.list_templates()
    return jsonify([
        {
            'id': t.template_id,
            'name': t.name,
            'description': t.description,
            'questions': len(t.form_schema.questions),
            'agents': len(t.agent_composition_rules),
            'cost_min': t.estimated_cost_range[0],
            'cost_max': t.estimated_cost_range[1],
        }
        for t in templates
    ])


@app.route('/api/templates/<template_id>')
def api_template_detail(template_id):
    """API endpoint to get template details."""
    template = registry.load_template(template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404

    return jsonify({
        'id': template.template_id,
        'name': template.name,
        'description': template.description,
        'form_schema': {
            'title': template.form_schema.title,
            'description': template.form_schema.description,
            'questions': [
                {
                    'id': q.id,
                    'text': q.text,
                    'type': q.type.value,
                    'options': q.options or [],
                    'required': q.required,
                    'help_text': q.help_text,
                }
                for q in template.form_schema.questions
            ]
        }
    })


INSPECT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inspect: {{ name }} - Empathy Framework</title>
    <style>
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --bg: #f9fafb;
            --card-bg: #ffffff;
            --text: #111827;
            --text-muted: #6b7280;
            --border: #e5e7eb;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }
        .container { max-width: 1000px; margin: 0 auto; padding: 2rem; }
        header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 2rem 0;
            margin-bottom: 2rem;
        }
        h1 { font-size: 2rem; margin-bottom: 0.5rem; }
        .back-link { color: rgba(255,255,255,0.8); text-decoration: none; }
        .back-link:hover { color: white; }
        .card {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }
        .card h2 { font-size: 1.25rem; margin-bottom: 1rem; color: var(--primary); }
        .meta { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
        .badge {
            padding: 0.25rem 0.75rem;
            background: var(--bg);
            border-radius: 6px;
            font-size: 0.875rem;
        }
        .question-item {
            padding: 1rem;
            background: var(--bg);
            border-radius: 8px;
            margin-bottom: 0.75rem;
        }
        .question-text { font-weight: 600; margin-bottom: 0.5rem; }
        .question-meta { font-size: 0.875rem; color: var(--text-muted); }
        .agent-item {
            padding: 1rem;
            background: var(--bg);
            border-radius: 8px;
            margin-bottom: 0.75rem;
        }
        pre {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <a href="/" class="back-link">← Back to Dashboard</a>
            <h1>{{ name }}</h1>
            <p>{{ description }}</p>
        </div>
    </header>
    <div class="container">
        <div class="card">
            <h2>Overview</h2>
            <div class="meta">
                <span class="badge">📋 {{ questions|length }} questions</span>
                <span class="badge">🤖 {{ agents|length }} agents</span>
                <span class="badge">💰 ${{ "%.2f"|format(cost_min) }}-${{ "%.2f"|format(cost_max) }}</span>
            </div>
            <p><strong>Template ID:</strong> <code>{{ template_id }}</code></p>
        </div>

        <div class="card">
            <h2>Questions</h2>
            {% for q in questions %}
            <div class="question-item">
                <div class="question-text">{{ loop.index }}. {{ q.text }}</div>
                <div class="question-meta">
                    Type: {{ q.type }} |
                    Required: {{ "Yes" if q.required else "No" }}
                    {% if q.options %} | Options: {{ q.options|length }}{% endif %}
                </div>
                {% if q.help_text %}<div class="question-meta" style="margin-top: 0.5rem;">{{ q.help_text }}</div>{% endif %}
            </div>
            {% endfor %}
        </div>

        <div class="card">
            <h2>Agent Composition Rules</h2>
            {% for agent in agents %}
            <div class="agent-item">
                <strong>{{ agent.agent_type }}</strong>
                {% if agent.condition %}<div class="question-meta">Condition: {{ agent.condition }}</div>{% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""


@app.route('/inspect/<template_id>')
def inspect_template(template_id):
    """Inspect page showing detailed template information."""
    template = registry.load_template(template_id)
    if not template:
        return "Template not found", 404

    return render_template_string(
        INSPECT_TEMPLATE,
        template_id=template.template_id,
        name=template.name,
        description=template.description,
        questions=[
            {
                'text': q.text,
                'type': q.type.value,
                'options': q.options or [],
                'required': q.required,
                'help_text': q.help_text,
            }
            for q in template.form_schema.questions
        ],
        agents=[
            {
                'agent_type': rule.agent_type,
                'condition': rule.condition,
            }
            for rule in template.agent_composition_rules
        ],
        cost_min=template.estimated_cost_range[0],
        cost_max=template.estimated_cost_range[1],
    )


if __name__ == '__main__':
    print("=" * 80)
    print("🚀 Empathy Framework - Meta-Workflow Dashboard")
    print("=" * 80)
    print()
    print("Starting web server...")
    print()
    print("📍 Open your browser to: http://localhost:8000")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 80)
    print()

    app.run(host='0.0.0.0', port=8000, debug=True)
