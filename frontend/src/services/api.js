import axios from 'axios';
import { config } from '../config';

// Create axios instance with defaults
const api = axios.create({
    baseURL: config.API_BASE_URL,
    timeout: 30000,
    headers: { 'Content-Type': 'application/json' }
});

// Request interceptor - attach auth token
api.interceptors.request.use((cfg) => {
    const token = localStorage.getItem('token');
    if (token) cfg.headers.Authorization = `Bearer ${token}`;
    return cfg;
});

// Response interceptor - handle auth errors
api.interceptors.response.use(
    (res) => res,
    (err) => {
        if (err.response?.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
        return Promise.reject(err);
    }
);

// ─── Recommendations ────────────────────────────────────────────
export const fetchRecommendations = async (params = {}) => {
    const prefs = JSON.parse(localStorage.getItem('user_preferences') || '{}');
    const { data } = await api.get('/recommendations/active', {
        params: { risk: prefs.risk, horizon: prefs.horizon, sectors: (prefs.sectors || []).join(','), ...params }
    });
    // Normalise: API may return an array directly or wrap it in { recommendations: [...] }
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.recommendations)) return data.recommendations;
    if (data && Array.isArray(data.data)) return data.data;
    return [];
};

export const fetchRecommendationById = async (id) => {
    const recs = await fetchRecommendations();
    return recs.find(r => r.id === id) || null;
};

// ─── Scan / Crawl ───────────────────────────────────────────────
export const fetchScanConfig = async () => {
    const { data } = await api.get('/scan/config');
    return data;
};

export const updateScanConfig = async (interval, enabled) => {
    const { data } = await api.post('/scan/config', null, { params: { interval, enabled } });
    return data;
};

export const triggerCrawl = async () => {
    const { data } = await api.post('/crawl', null);
    return data;
};

// ─── Trading / Portfolio ────────────────────────────────────────
export const fetchPortfolio = async () => {
    const { data } = await api.get('/trading/portfolio');
    return data;
};

export const fetchTradeHistory = async () => {
    const { data } = await api.get('/trading/history');
    return data;
};

// ─── Market Data ────────────────────────────────────────────────
export const fetchMarketStatus = async () => {
    const { data } = await api.get('/market/status');
    return data;
};

export const fetchOHLC = async (symbol, interval = '5m') => {
    const { data } = await api.get(`/market/ohlc/${symbol}`, { params: { interval } });
    return data;
};

export const fetchBatchQuotes = async (symbols) => {
    if (!symbols || symbols.length === 0) return {};
    const { data } = await api.get('/market/quotes/batch', { params: { symbols: symbols.join(',') } });
    return data;  // { RELIANCE: { ltp: 2500.0, ... }, TATASTEEL: { ltp: 145.0, ... } }
};

// ─── Watchlist ──────────────────────────────────────────────────
export const fetchWatchlist = async () => {
    const saved = JSON.parse(localStorage.getItem('watchlist') || '[]');
    return saved;
};

export const addToWatchlist = (symbol) => {
    const list = JSON.parse(localStorage.getItem('watchlist') || '[]');
    if (!list.includes(symbol)) {
        list.push(symbol);
        localStorage.setItem('watchlist', JSON.stringify(list));
    }
    return list;
};

export const removeFromWatchlist = (symbol) => {
    let list = JSON.parse(localStorage.getItem('watchlist') || '[]');
    list = list.filter(s => s !== symbol);
    localStorage.setItem('watchlist', JSON.stringify(list));
    return list;
};

// ─── Alerts ─────────────────────────────────────────────────────
export const fetchAlerts = async () => {
    try {
        const { data } = await api.get('/alerts/active');
        return data;
    } catch {
        // Fallback: derive from recommendations
        const recs = await fetchRecommendations();
        return recs.map(r => ({
            id: r.id,
            type: isBullishDir(r.direction) ? 'LONG Signal' : 'SHORT Signal',
            symbol: r.symbol,
            message: `${isBullishDir(r.direction) ? 'Buy' : 'Sell'} signal at ₹${r.entry || r.price || '—'} | Conviction: ${(r.conviction || 0).toFixed(1)}%`,
            time: r.created_at || r.timestamp || r.expires_at || new Date().toISOString(),
            severity: (r.conviction || 0) > 25 ? 'high' : 'medium',
            direction: r.direction,
            conviction: r.conviction || 0,
            entry: r.entry || r.price || 0,
            target1: r.target1 || 0,
            sl: r.sl || 0
        }));
    }
};

// Helper used only in this module
const isBullishDir = (d) => d === 'UP' || d === 'Strong Up' || d === 'LONG';

// ─── Auth ───────────────────────────────────────────────────────
export const fetchUser = async () => {
    const { data } = await api.get('/auth/me');
    return data;
};

export const loginUser = async (credential) => {
    const { data } = await api.post('/auth/login', { token: credential });
    return data;
};

export const loginWithEmail = async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password });
    return data;
};

export const registerUser = async (email, password, confirmPassword, fullName) => {
    const { data } = await api.post('/auth/register', {
        email,
        password,
        confirm_password: confirmPassword,
        full_name: fullName,
    });
    return data;
};

export const verifyOtp = async (email, otp) => {
    const { data } = await api.post('/auth/verify-otp', { email, otp });
    return data;
};

export const resendOtp = async (email) => {
    const { data } = await api.post('/auth/resend-otp', { email });
    return data;
};

export const getPasswordRules = async () => {
    const { data } = await api.get('/auth/password-rules');
    return data;
};

// ─── Intraday Agent ─────────────────────────────────────────────
export const fetchAgentStatus = async () => {
    try {
        const { data } = await api.get('/agent/status');
        return data;
    } catch {
        return { status: 'offline', active_monitors: 0 };
    }
};

export const fetchAgentTrades = async () => {
    try {
        const { data } = await api.get('/agent/trades');
        return data;
    } catch {
        return [];
    }
};

// ─── Model Performance Report (Admin) ───────────────────────────
export const fetchModelReport = async () => {
    const { data } = await api.get('/trading/model/report');
    return data;
};

export const fetchFailedTrades = async () => {
    const { data } = await api.get('/trading/model/failed-trades');
    return data;
};

export const submitModelFeedback = async (feedback, category = 'general') => {
    const { data } = await api.post('/trading/model/feedback', { feedback, category });
    return data;
};

export const fetchModelFeedback = async () => {
    const { data } = await api.get('/trading/model/feedback');
    return data;
};

// ─── Options Scalping ───────────────────────────────────────────
export const fetchOptionsSpot = async () => {
    const { data } = await api.get('/options/spot');
    return data;
};

export const fetchOptionsChain = async () => {
    const { data } = await api.get('/options/chain');
    return data;
};

export const fetchScalpSignal = async () => {
    const { data } = await api.get('/options/signal');
    return data;
};

export const fetchOptionsPortfolio = async () => {
    const { data } = await api.get('/options/portfolio');
    return data;
};

export const fetchOptionsDailyStats = async () => {
    const { data } = await api.get('/options/stats/daily');
    return data;
};

export const placeOptionsTrade = async (payload) => {
    const { data } = await api.post('/options/trade/place', payload);
    return data;
};

export const closeOptionsTrade = async (tradeId) => {
    const { data } = await api.post('/options/trade/close', { trade_id: tradeId });
    return data;
};

export const resetOptionsPortfolio = async () => {
    const { data } = await api.post('/options/portfolio/reset');
    return data;
};

export const fetchAutoTradeStatus = async () => {
    const { data } = await api.get('/options/auto-trade/status');
    return data;
};

export const toggleAutoTrade = async () => {
    const { data } = await api.post('/options/auto-trade/toggle');
    return data;
};

export const fetchLearningStats = async () => {
    const { data } = await api.get('/options/learning/stats');
    return data;
};

export const resetLearning = async () => {
    const { data } = await api.post('/options/learning/reset');
    return data;
};

export default api;
