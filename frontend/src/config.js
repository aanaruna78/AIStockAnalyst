const API_BASE_URL = 'http://localhost:8010/api/v1';
const WS_BASE_URL = 'ws://localhost:8010/api/v1';

export const config = {
    API_BASE_URL,
    WS_BASE_URL,
    endpoints: {
        auth: {
            login: `${API_BASE_URL}/auth/login`,
            me: `${API_BASE_URL}/auth/me`,
            signup: `${API_BASE_URL}/auth/signup`
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
