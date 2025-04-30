let chartInstance = null;
let currentEventSource = null;
let currentQuestion = '';
let currentSQL = '';
let historyList = [];

// 初始化事件监听
document.querySelectorAll('.sample-question').forEach(button => {
    button.addEventListener('click', (e) => {
        const question = e.target.textContent;
        document.getElementById('questionInput').value = question;
        document.getElementById('askButton').click();
    });
});

document.getElementById('askButton').addEventListener('click', () => {
    resetAnalysisState();
    const question = document.getElementById('questionInput').value;
    if (!question) {
        showToast('问题不能为空', 'error');
        return;
    }

    resetAnalysisState();
    currentQuestion = question;

    // 添加历史问题
    addHistoryQuestion(question);

    document.querySelector('.loading').style.display = 'block';
    document.getElementById('askButton').style.display = 'none';
    document.getElementById('stopButton').style.display = 'inline-block';

    currentEventSource = new EventSource(`/ask?question=${encodeURIComponent(question)}`);

    currentEventSource.addEventListener('table', (e) => {
        const data = JSON.parse(e.data)
        renderTable(data);
    });

    currentEventSource.addEventListener('sql', (e) => {
        const data = JSON.parse(e.data);
        currentSQL = data.sql; // 保存当前 SQL
        console.log('Received SQL:', currentSQL); // 调试用
    });

    currentEventSource.addEventListener('echarts', (e) => {
        const config = JSON.parse(e.data);
        renderChart(config);
    });

    currentEventSource.addEventListener('analysis_chunk', (e) => {
        const data = JSON.parse(e.data);
        const container = document.getElementById('analysisContainer');
        container.textContent += data.chunk;
        container.scrollTop = container.scrollHeight;
    });

    currentEventSource.addEventListener('analysis_complete', (e) => {
        document.querySelector('.feedback-buttons').style.display = 'block';
    });

    currentEventSource.addEventListener('error', (e) => {
        showToast(`分析出错: ${e.data}`, 'error');
        cleanupAfterCompletion();
    });

    currentEventSource.addEventListener('done', () => {
        cleanupAfterCompletion();
    });
});

// 反馈功能逻辑
document.querySelector('.yes-btn').addEventListener('click', (e) => {
    // 立即禁用按钮
    e.target.disabled = true;
    document.querySelector('.no-btn').disabled = true;

    // 添加加载状态
    e.target.innerHTML = '<div class="mini-loader"></div> 提交中...';

    submitFeedback(null, 1);
});

document.querySelector('.no-btn').addEventListener('click', () => {
    document.getElementById('feedbackModal').style.display = 'block';
});

document.querySelector('.close').addEventListener('click', () => {
    document.getElementById('feedbackModal').style.display = 'none';
});

document.getElementById('submitFeedback').addEventListener('click', () => {
    const feedback = document.getElementById('feedbackInput').value;
    if (!feedback) {
        showToast('请填写反馈内容', 'error');
        return;
    }
    submitFeedback(feedback, 0);
    document.getElementById('feedbackModal').style.display = 'none';
    document.getElementById('feedbackInput').value = '';
});

// 通用功能函数
function resetAnalysisState() {
    // 重置反馈按钮状态
    const buttons = document.querySelector('.feedback-buttons');
    buttons.style.display = 'block'; // 强制显示容器
    buttons.classList.remove('hidden'); // 移除透明状态
    buttons.style.opacity = '1'; // 确保完全可见
    buttons.style.pointerEvents = 'auto'; // 恢复点击事件

    // 重置按钮内容和状态
    document.querySelectorAll('.feedback-btn').forEach(btn => {
        btn.disabled = false;
        btn.innerHTML = btn.dataset.originalText;
    });

    // 其他重置逻辑保持不变...
    ['tableContainer', 'analysisContainer'].forEach(id => {
        document.getElementById(id).innerHTML = '';
    });
    if (chartInstance) {
        chartInstance.dispose();
        chartInstance = null;
    }
}

function cleanupAfterCompletion() {
    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }
    document.querySelector('.loading').style.display = 'none';
    document.getElementById('askButton').style.display = 'inline-block';
    document.getElementById('stopButton').style.display = 'none';
}

function renderTable(data) {
    const container = document.getElementById('tableContainer');
    const table = document.createElement('table');

    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    Object.keys(data[0]).forEach(key => {
        const th = document.createElement('th');
        th.textContent = key;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    data.forEach(row => {
        const tr = document.createElement('tr');
        Object.values(row).forEach(value => {
            const td = document.createElement('td');
            td.textContent = value;
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    container.innerHTML = '';
    container.appendChild(table);
}

function renderChart(config) {
    const chartDom = document.getElementById('chartContainer');
    chartInstance = echarts.init(chartDom);
    chartInstance.setOption(config);

    window.addEventListener('resize', () => {
        chartInstance.resize();
    });
}

// 修改后的提交函数
function submitFeedback(feedback, isCorrect) {
    // 获取按钮容器
    const buttons = document.querySelector('.feedback-buttons');

    fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            question: currentQuestion,
            sql: currentSQL,
            feedback: feedback,
            is_correct: isCorrect
        })
    })
        .finally(() => { // 无论成功失败都隐藏
            buttons.classList.add('hidden');
            // 重置按钮状态（为下次分析准备）
            setTimeout(() => {
                buttons.style.display = 'none';
                document.querySelectorAll('.feedback-btn').forEach(btn => {
                    btn.disabled = false;
                    btn.innerHTML = btn.dataset.originalText;
                });
            }, 300);
        })
        .then(response => {
            if (!response.ok) throw new Error('提交失败');
            showToast(isCorrect ? '感谢反馈！' : '问题已记录', 'success');
        })
        .catch(error => {
            showToast(error.message, 'error');
        });
}

// 在页面加载时保存按钮原始状态
window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.feedback-btn').forEach(btn => {
        btn.dataset.originalText = btn.innerHTML;
    });
    // 加载历史问题
    loadHistoryQuestions();
    // 绑定清除历史问题按钮事件
    document.getElementById('clearHistoryButton').addEventListener('click', clearHistoryQuestions);
});

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

document.getElementById('stopButton').addEventListener('click', () => {
    if (currentEventSource) {
        currentEventSource.close();
        showToast('已中止当前分析任务', 'warning');
    }
    cleanupAfterCompletion();
});

// 添加历史问题
function addHistoryQuestion(question) {
    historyList.unshift(question);
    if (historyList.length > 20) {
        historyList.pop();
    }
    saveHistoryQuestions();
    renderHistoryQuestions();
}

// 保存历史问题到本地存储
function saveHistoryQuestions() {
    localStorage.setItem('historyQuestions', JSON.stringify(historyList));
}

// 加载历史问题从本地存储
function loadHistoryQuestions() {
    const storedHistory = localStorage.getItem('historyQuestions');
    if (storedHistory) {
        historyList = JSON.parse(storedHistory);
        renderHistoryQuestions();
    }
}

// 渲染历史问题
function renderHistoryQuestions() {
    const historyListElement = document.getElementById('historyList');
    historyListElement.innerHTML = '';
    historyList.forEach(question => {
        const li = document.createElement('li');
        li.className = 'history-item';
        li.textContent = question;
        li.addEventListener('click', () => {
            document.getElementById('questionInput').value = question;
            document.getElementById('askButton').click();
        });
        historyListElement.appendChild(li);
    });
}

// 清除历史问题
function clearHistoryQuestions() {
    historyList = [];
    saveHistoryQuestions();
    renderHistoryQuestions();
    showToast('历史问题已清除', 'success');
}