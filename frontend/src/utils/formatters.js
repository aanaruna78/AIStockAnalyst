// Format Indian currency
export const formatINR = (value, decimals = 2) => {
    if (value == null || isNaN(value)) return '₹---';
    return '₹' + Number(value).toLocaleString('en-IN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
};

// Format percentage
export const formatPercent = (value, decimals = 1) => {
    if (value == null || isNaN(value)) return '---';
    const sign = value > 0 ? '+' : '';
    return `${sign}${Number(value).toFixed(decimals)}%`;
};

// Get P&L color
export const getPnlColor = (value) => {
    if (value > 0) return '#10b981'; // green
    if (value < 0) return '#ef4444'; // red
    return 'text.secondary';
};

// Direction helpers
export const isBullish = (direction) =>
    direction === 'UP' || direction === 'Strong Up' || direction === 'LONG';

export const getDirectionColor = (direction) =>
    isBullish(direction) ? '#10b981' : '#ef4444';

export const getDirectionBg = (direction) =>
    isBullish(direction) ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)';

export const getDirectionLabel = (direction) =>
    isBullish(direction) ? 'LONG' : 'SHORT';

// Relative time
export const timeAgo = (timestamp) => {
    if (!timestamp) return '';
    const diff = (Date.now() - new Date(timestamp).getTime()) / 1000;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
};

// Conviction level
export const getConvictionLevel = (value) => {
    if (value >= 30) return { label: 'HIGH', color: '#10b981' };
    if (value >= 20) return { label: 'MEDIUM', color: '#f59e0b' };
    return { label: 'LOW', color: '#6b7280' };
};

// Score breakdown color mapping
export const SCORE_COLORS = {
    'Sentiment': '#06b6d4',
    'Technical': '#f59e0b',
    'AI Model': '#10b981',
    'Fundamental': '#a855f7',
    'Analyst': '#ef4444'
};

// Truncate text
export const truncate = (str, len = 80) => {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
};
