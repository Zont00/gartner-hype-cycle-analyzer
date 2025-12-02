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
            handleErrorResponse(response.status, errorData);
            return;
        }

        const data = await response.json();
        displayResults(data);
    } catch (error) {
        showError(`Network Error: ${error.message}. Please check your internet connection and ensure the backend is running.`);
    } finally {
        document.getElementById('loading').classList.add('hidden');
    }
}

function handleErrorResponse(status, errorData) {
    let errorMessage = '';

    switch (status) {
        case 422:
            // Validation error
            if (Array.isArray(errorData.detail)) {
                const validationErrors = errorData.detail.map(err =>
                    `${err.loc.join('.')}: ${err.msg}`
                ).join(', ');
                errorMessage = `Invalid input: ${validationErrors}`;
            } else {
                errorMessage = `Invalid input: ${errorData.detail}`;
            }
            break;
        case 503:
            // Insufficient data
            errorMessage = `Service temporarily unavailable: ${errorData.detail}. Please try again later or try a different keyword.`;
            break;
        case 500:
            // Internal server error
            errorMessage = `Analysis failed: ${errorData.detail}. Please try again or contact support if the issue persists.`;
            break;
        default:
            errorMessage = `Error (${status}): ${errorData.detail || 'Unknown error occurred'}`;
    }

    showError(errorMessage);
}

function displayResults(data) {
    document.getElementById('result-keyword').textContent = data.keyword;
    document.getElementById('phase').textContent = formatPhase(data.phase);
    document.getElementById('confidence').textContent = `${(data.confidence * 100).toFixed(1)}%`;
    document.getElementById('reasoning').textContent = data.reasoning;

    // Display status indicators
    displayStatusIndicators(data);

    // Show partial data warning if applicable
    if (data.partial_data) {
        const warningBanner = document.getElementById('partial-data-warning');
        const warningMessage = document.getElementById('partial-data-message');
        warningMessage.textContent = `This analysis was performed with partial data (${data.collectors_succeeded}/5 collectors succeeded). Results may be less reliable.`;
        warningBanner.classList.remove('hidden');

        // Display errors if available
        if (data.errors && data.errors.length > 0) {
            warningMessage.textContent += ` Issues: ${data.errors.join('; ')}`;
        }
    } else {
        document.getElementById('partial-data-warning').classList.add('hidden');
    }

    // Draw hype cycle curve with position marker
    drawHypeCycle(data.phase);

    // Display per-source analyses
    displayPerSourceAnalyses(data.per_source_analyses);

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

function displayStatusIndicators(data) {
    const container = document.getElementById('status-indicators');
    container.innerHTML = ''; // Clear previous content

    const indicators = [];

    // Cache status
    if (data.cache_hit) {
        const cacheTime = new Date(data.timestamp).toLocaleString();
        indicators.push({
            className: 'status-badge status-cache',
            text: `📦 Cached result from ${cacheTime}`
        });
    } else {
        indicators.push({
            className: 'status-badge status-fresh',
            text: '🔍 Fresh analysis'
        });
    }

    // Collectors count
    indicators.push({
        className: 'status-badge status-collectors',
        text: `📊 Based on ${data.collectors_succeeded}/5 data sources`
    });

    // Expiration time (for cached results)
    if (data.cache_hit && data.expires_at) {
        const expiresAt = new Date(data.expires_at);
        const now = new Date();
        const hoursUntilExpiry = Math.round((expiresAt - now) / (1000 * 60 * 60));
        indicators.push({
            className: 'status-badge status-expiry',
            text: `⏰ Expires in ~${hoursUntilExpiry} hours`
        });
    }

    // Create badge elements
    indicators.forEach(indicator => {
        const badge = document.createElement('span');
        badge.className = indicator.className;
        badge.textContent = indicator.text;
        container.appendChild(badge);
    });
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

function displayPerSourceAnalyses(perSourceAnalyses) {
    const container = document.getElementById('per-source-breakdowns');
    container.innerHTML = ''; // Clear previous content

    if (!perSourceAnalyses) {
        container.innerHTML = '<p class="no-data">Per-source analyses not available</p>';
        return;
    }

    // Map source keys to display names
    const sourceDisplayNames = {
        'social': 'Social Media (Hacker News)',
        'papers': 'Research Papers (Semantic Scholar)',
        'patents': 'Patents (PatentsView)',
        'news': 'News Coverage (GDELT)',
        'finance': 'Financial Markets (Yahoo Finance)'
    };

    // Create a card for each source
    Object.keys(perSourceAnalyses).forEach(sourceKey => {
        const analysis = perSourceAnalyses[sourceKey];
        const sourceName = sourceDisplayNames[sourceKey] || sourceKey;

        const sourceCard = document.createElement('div');
        sourceCard.className = 'source-card';

        const sourceHeader = document.createElement('div');
        sourceHeader.className = 'source-header';

        const sourceTitleSpan = document.createElement('span');
        sourceTitleSpan.className = 'source-name';
        sourceTitleSpan.textContent = sourceName;

        const phaseBadge = document.createElement('span');
        phaseBadge.className = `phase-badge phase-${analysis.phase}`;
        phaseBadge.textContent = formatPhase(analysis.phase);

        const confidenceBadge = document.createElement('span');
        confidenceBadge.className = `confidence-badge ${getConfidenceClass(analysis.confidence)}`;
        confidenceBadge.textContent = `${(analysis.confidence * 100).toFixed(0)}%`;

        sourceHeader.appendChild(sourceTitleSpan);
        sourceHeader.appendChild(phaseBadge);
        sourceHeader.appendChild(confidenceBadge);

        const reasoningDiv = document.createElement('div');
        reasoningDiv.className = 'source-reasoning';
        reasoningDiv.textContent = analysis.reasoning;

        sourceCard.appendChild(sourceHeader);
        sourceCard.appendChild(reasoningDiv);
        container.appendChild(sourceCard);
    });
}

function getConfidenceClass(confidence) {
    if (confidence >= 0.8) return 'confidence-high';
    if (confidence >= 0.6) return 'confidence-medium';
    return 'confidence-low';
}

function getPhaseColor(phase) {
    const phaseColors = {
        'innovation_trigger': '#3b82f6', // blue
        'peak': '#ef4444', // red
        'trough': '#f97316', // orange
        'slope': '#eab308', // yellow
        'plateau': '#22c55e' // green
    };
    return phaseColors[phase] || '#6b7280';
}
