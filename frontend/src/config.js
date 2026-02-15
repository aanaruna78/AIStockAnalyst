const getDefaultApiBaseUrl = () => {
    if (typeof window === 'undefined') {
        return 'http://localhost:8000/api/v1';
    }
    return `${window.location.origin}/api/v1`;
};

const getDefaultWsBaseUrl = () => {
    if (typeof window === 'undefined') {
        return 'ws://localhost:8000/api/v1';
    }
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${window.location.host}/api/v1`;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || getDefaultApiBaseUrl();
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || getDefaultWsBaseUrl();

export const config = {
    API_BASE_URL,
    WS_BASE_URL,
    endpoints: {
        auth: {
            login: `${API_BASE_URL}/auth/login`,
            register: `${API_BASE_URL}/auth/register`,
            verifyOtp: `${API_BASE_URL}/auth/verify-otp`,
            resendOtp: `${API_BASE_URL}/auth/resend-otp`,
            passwordRules: `${API_BASE_URL}/auth/password-rules`,
            me: `${API_BASE_URL}/auth/me`,
            signup: `${API_BASE_URL}/auth/signup`,
            google: `${API_BASE_URL}/auth/google`,
            preferences: `${API_BASE_URL}/auth/preferences`,
        },
        recommendations: {
            active: `${API_BASE_URL}/recommendations/active`,
            ws: `${WS_BASE_URL}/recommendations/ws`
        },
        scan: {
            config: `${API_BASE_URL}/scan/config`,
            base: `${API_BASE_URL}`,
            progress: `${WS_BASE_URL}/progress`,
            crawl: `${API_BASE_URL}/crawl`
        },
        trading: {
            portfolio: `${API_BASE_URL}/trading/portfolio`
        }
    }
};

export default config;
