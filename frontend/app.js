const API_BASE_URL = 'http://localhost:8000/api';

// Handle analyze button click
document.getElementById('analyze-btn').addEventListener('click', async () => {
    const keyword = document.getElementById('keyword').value.trim();
    if (!keyword) {
        showError('Please enter a technology keyword');
        return;
    }

    await analyzeKeyword(keyword);
});

// Handle enter key in input field
document.getElementById('keyword').addEventListener('keypress', async (e) => {
    if (e.key === 'Enter') {
        const keyword = e.target.value.trim();
        if (keyword) {
            await analyzeKeyword(keyword);
        }
    }
});

async function analyzeKeyword(keyword) {
    // Show loading state
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('results').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');

    try {
        // Call FastAPI backend
        const response = await fetch(`${API_BASE_URL}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Analysis failed');
        }

        const data = await response.json();
        displayResults(data);
    } catch (error) {
        showError(`Error: ${error.message}`);
    } finally {
        document.getElementById('loading').classList.add('hidden');
    }
}

function displayResults(data) {
    document.getElementById('result-keyword').textContent = data.keyword;
    document.getElementById('phase').textContent = formatPhase(data.phase);
    document.getElementById('confidence').textContent = `${(data.confidence * 100).toFixed(1)}%`;
    document.getElementById('reasoning').textContent = data.reasoning;

    // Draw hype cycle curve with position marker
    drawHypeCycle(data.phase);

    document.getElementById('results').classList.remove('hidden');
}

function formatPhase(phase) {
    const phaseNames = {
        'innovation_trigger': 'Innovation Trigger',
        'peak': 'Peak of Inflated Expectations',
        'trough': 'Trough of Disillusionment',
        'slope': 'Slope of Enlightenment',
        'plateau': 'Plateau of Productivity'
    };
    return phaseNames[phase] || phase;
}

function showError(message) {
    const errorElement = document.getElementById('error');
    errorElement.textContent = message;
    errorElement.classList.remove('hidden');
}

function drawHypeCycle(phase) {
    const canvas = document.getElementById('hype-cycle-canvas');
    const ctx = canvas.getContext('2d');

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Define hype cycle curve points
    const points = [
        { x: 50, y: 350, phase: 'innovation_trigger' },
        { x: 200, y: 100, phase: 'peak' },
        { x: 400, y: 350, phase: 'trough' },
        { x: 600, y: 200, phase: 'slope' },
        { x: 750, y: 180, phase: 'plateau' }
    ];

    // Draw curve
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        const cp1x = points[i - 1].x + (points[i].x - points[i - 1].x) / 2;
        const cp1y = points[i - 1].y;
        const cp2x = points[i].x - (points[i].x - points[i - 1].x) / 2;
        const cp2y = points[i].y;
        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, points[i].x, points[i].y);
    }
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Draw position marker
    const currentPoint = points.find(p => p.phase === phase);
    if (currentPoint) {
        ctx.beginPath();
        ctx.arc(currentPoint.x, currentPoint.y, 10, 0, 2 * Math.PI);
        ctx.fillStyle = '#ef4444';
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
    }

    // Draw labels
    ctx.fillStyle = '#1f2937';
    ctx.font = '12px sans-serif';
    ctx.fillText('Innovation', 30, 370);
    ctx.fillText('Peak', 180, 90);
    ctx.fillText('Trough', 370, 370);
    ctx.fillText('Slope', 580, 190);
    ctx.fillText('Plateau', 720, 170);
}
