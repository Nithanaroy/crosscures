import { state } from './state.js';
import { submitQuestionResponse } from './api.js';
import { renderSidePanel } from './tree.js';
import { completeQuestionnaire } from './summary.js';

export function displayQuestion() {
    if (!state.currentQuestion) {
        completeQuestionnaire();
        return;
    }

    const currentCount = state.answeredCount + 1;
    const total = state.sessionData.totalQuestions;

    document.getElementById('questionNumber').textContent = `Question ${currentCount}/${total}`;

    const progress = (currentCount / total) * 100;
    document.getElementById('progressFill').style.width = progress + '%';

    document.getElementById('questionText').textContent = state.currentQuestion.question_text;

    const container = document.getElementById('answerContainer');
    container.innerHTML = '';

    switch (state.currentQuestion.question_type) {
        case 'yes_no':
            displayYesNo(container);
            break;
        case 'scale_1_10':
            displayScale(container);
            break;
        case 'multiple_choice':
            displayMultipleChoice(container);
            break;
        case 'text':
            displayText(container);
            break;
    }

    updateNavigationButtons();
}

function displayYesNo(container) {
    container.innerHTML = `
        <div class="yes-no-buttons">
            <button class="btn" onclick="window._recordResponse(true, 'Yes')">Yes</button>
            <button class="btn" onclick="window._recordResponse(false, 'No')">No</button>
        </div>
    `;
}

function displayScale(container) {
    let html = '<div class="question-type-scale">';
    for (let i = 1; i <= 10; i++) {
        html += `<button class="scale-btn" onclick="window._recordResponse(${i}, '${i}')">${i}</button>`;
    }
    html += '</div>';
    container.innerHTML = html;
}

function displayMultipleChoice(container) {
    let html = '<div class="question-options">';
    state.currentQuestion.options.forEach(option => {
        html += `<button class="option-btn" onclick="window._recordResponse('${option}', '${option}')">${option}</button>`;
    });
    html += '</div>';
    container.innerHTML = html;
}

function displayText(container) {
    container.innerHTML = `
        <textarea class="text-input" id="textInput" placeholder="Enter your response..."></textarea>
    `;
}

export function recordResponse(value, display) {
    state.allResponses[state.currentQuestion.question_id] = value;

    const container = document.getElementById('answerContainer');
    container.querySelectorAll('.selected').forEach(el => el.classList.remove('selected'));
    event.target.classList.add('selected');

    document.getElementById('nextBtn').style.display = 'block';
    document.getElementById('completeBtn').style.display = 'none';
}

export async function submitResponse() {
    if (state.submitting) return;
    state.submitting = true;

    try {
        let responseValue;

        if (state.currentQuestion.question_type === 'text') {
            responseValue = document.getElementById('textInput').value;
            if (!responseValue.trim()) {
                alert('Please enter a response');
                return;
            }
        } else {
            if (!(state.currentQuestion.question_id in state.allResponses)) {
                alert('Please select an answer');
                return;
            }
            responseValue = state.allResponses[state.currentQuestion.question_id];
        }

        const data = await submitQuestionResponse(
            state.currentSessionId,
            state.currentQuestion.question_id,
            responseValue
        );

        state.answeredQuestions[state.currentQuestion.question_id] = responseValue;

        if (data.skipped_questions) {
            data.skipped_questions.forEach(qId => state.skippedQuestions.add(qId));
        }

        // Update question tree if backend sent a revised plan (LLM mode)
        if (data.updated_question_tree) {
            state.questionTree = data.updated_question_tree;
            state.sessionData.totalQuestions = data.updated_question_tree.length;
        }

        state.answeredCount++;
        state.currentQuestion = data.next_question;

        // If LLM mode returned reasoning for the next question, record it
        if (data.reasoning && data.next_question && state.generatorMode === 'llm') {
            state.reasoningHistory.push({
                question_id: data.next_question.question_id,
                question_text: data.next_question.question_text,
                reasoning: data.reasoning,
            });
        }

        if (data.is_complete) {
            state.questionTree.forEach(node => {
                if (node.depends_on_question_id &&
                    !(node.question_id in state.answeredQuestions) &&
                    !state.skippedQuestions.has(node.question_id)) {
                    state.skippedQuestions.add(node.question_id);
                }
            });
            renderSidePanel();
            await completeQuestionnaire();
        } else {
            renderSidePanel();
            displayQuestion();
        }
    } catch (error) {
        console.error('Error submitting response:', error);
        alert('Error submitting response');
    } finally {
        state.submitting = false;
    }
}

function updateNavigationButtons() {
    const hasResponse = state.currentQuestion.question_id in state.allResponses ||
                        state.currentQuestion.question_type === 'text';

    document.getElementById('nextBtn').style.display = 'none';
    document.getElementById('completeBtn').style.display = 'none';

    if (hasResponse) {
        const currentCount = state.answeredCount + 1;
        const total = state.sessionData.totalQuestions;

        if (currentCount >= total) {
            document.getElementById('completeBtn').style.display = 'block';
        } else {
            document.getElementById('nextBtn').style.display = 'block';
        }
    }
}
