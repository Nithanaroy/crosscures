import { state } from './state.js';
import { formatAnswer } from './summary.js';

export function toggleTreePanel() {
    state.treePanelOpen = !state.treePanelOpen;
    const panel = document.getElementById('treePanel');
    const btn = document.getElementById('treeToggleBtn');
    if (state.treePanelOpen) {
        panel.classList.add('open');
        btn.textContent = state.generatorMode === 'llm' ? 'Hide Reasoning' : 'Hide Tree';
    } else {
        panel.classList.remove('open');
        btn.textContent = state.generatorMode === 'llm' ? 'Show Reasoning' : 'Show Tree';
    }
}

export function resetTreePanel() {
    document.getElementById('treePanel').classList.remove('open');
    document.getElementById('treeToggleBtn').textContent = 'Show Tree';
}

export function renderSidePanel() {
    if (state.generatorMode === 'llm') {
        renderReasoning();
    } else {
        renderTree();
    }
    // Toggle legend visibility based on mode
    const legend = document.querySelector('.tree-legend');
    if (legend) {
        legend.style.display = state.generatorMode === 'llm' ? 'none' : 'flex';
    }
}

export function renderTree() {
    const container = document.getElementById('treeContent');
    if (!state.questionTree.length) {
        container.innerHTML = '<div style="color:#999;font-size:12px;">No tree data</div>';
        return;
    }

    const tagOrder = ['base', 'diabetes', 'hypertension', 'cardiac', 'respiratory'];
    const tagLabels = {
        base: 'Base Questions',
        diabetes: 'Diabetes',
        hypertension: 'Hypertension',
        cardiac: 'Cardiac',
        respiratory: 'Respiratory',
    };

    const groups = {};
    state.questionTree.forEach(node => {
        const tag = node.condition_tag || 'base';
        if (!groups[tag]) groups[tag] = [];
        groups[tag].push(node);
    });

    let html = '';
    // Use tagOrder for known tags, then any remaining
    const allTags = [...new Set([...tagOrder.filter(t => groups[t]), ...Object.keys(groups)])];
    allTags.forEach(tag => {
        if (!groups[tag]) return;
        html += '<div class="tree-section">';
        html += '<div class="tree-section-label">' + (tagLabels[tag] || tag) + '</div>';
        groups[tag].forEach(node => {
            const nodeState = getNodeState(node);

            if (node.depends_on_question_id && node.trigger_label) {
                html += '<div class="tree-branch-label">' + node.trigger_label + '</div>';
            }

            html += '<div class="tree-node ' + nodeState + '">';
            html += '<div class="tree-node-icon">' + getNodeIcon(nodeState) + '</div>';
            html += '<div class="tree-node-text">';
            html += '<div class="tree-node-label">' + truncate(node.question_text, 50) + '</div>';

            if (nodeState === 'answered') {
                const val = state.answeredQuestions[node.question_id];
                html += '<div class="tree-node-answer">' + formatAnswer(val) + '</div>';
            } else if (nodeState === 'skipped') {
                html += '<div class="tree-node-skip-reason">Skipped: condition not met</div>';
            }

            html += '</div></div>';
        });
        html += '</div>';
    });

    container.innerHTML = html;
}

function renderReasoning() {
    const container = document.getElementById('treeContent');
    if (!state.reasoningHistory.length) {
        container.innerHTML = '<div class="reasoning-empty">LLM reasoning will appear here as questions are asked.</div>';
        return;
    }

    let html = '<div class="reasoning-thread">';
    state.reasoningHistory.forEach((entry, index) => {
        const isCurrent = state.currentQuestion &&
            entry.question_id === state.currentQuestion.question_id;
        const isAnswered = entry.question_id in state.answeredQuestions;
        const stateClass = isCurrent ? 'reasoning-current' : (isAnswered ? 'reasoning-answered' : '');

        html += '<div class="reasoning-entry ' + stateClass + '">';
        html += '<div class="reasoning-step">Step ' + (index + 1) + '</div>';
        html += '<div class="reasoning-question">' + truncate(entry.question_text, 80) + '</div>';
        html += '<div class="reasoning-text">' + escapeHtml(entry.reasoning) + '</div>';

        if (isAnswered) {
            const val = state.answeredQuestions[entry.question_id];
            html += '<div class="reasoning-answer">Patient answered: ' + formatAnswer(val) + '</div>';
        }

        html += '</div>';
    });
    html += '</div>';

    container.innerHTML = html;
    // Auto-scroll to latest
    container.scrollTop = container.scrollHeight;
}

function getNodeState(node) {
    if (node.question_id in state.answeredQuestions) return 'answered';
    if (state.skippedQuestions.has(node.question_id)) return 'skipped';
    if (state.currentQuestion && node.question_id === state.currentQuestion.question_id) return 'current';
    return 'upcoming';
}

function getNodeIcon(nodeState) {
    switch (nodeState) {
        case 'answered': return 'OK';
        case 'current': return '?';
        case 'skipped': return '--';
        case 'upcoming': return '';
        default: return '';
    }
}

function truncate(text, max) {
    return text.length > max ? text.substring(0, max) + '...' : text;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
