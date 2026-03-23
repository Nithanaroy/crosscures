import { state } from './state.js';
import { formatAnswer } from './summary.js';

export function toggleTreePanel() {
    state.treePanelOpen = !state.treePanelOpen;
    const panel = document.getElementById('treePanel');
    const btn = document.getElementById('treeToggleBtn');
    if (state.treePanelOpen) {
        panel.classList.add('open');
        btn.textContent = 'Hide Tree';
    } else {
        panel.classList.remove('open');
        btn.textContent = 'Show Tree';
    }
}

export function resetTreePanel() {
    document.getElementById('treePanel').classList.remove('open');
    document.getElementById('treeToggleBtn').textContent = 'Show Tree';
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
    tagOrder.forEach(tag => {
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
