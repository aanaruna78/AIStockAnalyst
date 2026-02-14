import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchRecommendations, fetchScanConfig, updateScanConfig, triggerCrawl } from '../services/api';
import { config } from '../config';

export const useRecommendations = () => {
    const [recommendations, setRecommendations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [scanConfig, setScanConfig] = useState({ interval_minutes: 10, enabled: true, last_scan_time: null });
    const [crawling, setCrawling] = useState(false);
    const [crawlProgress, setCrawlProgress] = useState(null);
    const [logs, setLogs] = useState([]);

    const load = useCallback(async () => {
        try {
            setLoading(true);
            const [recs, cfg] = await Promise.all([fetchRecommendations(), fetchScanConfig()]);
            setRecommendations(recs || []);
            setScanConfig(cfg);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();

        // Recommendations WebSocket
        let recWs;
        try {
            recWs = new WebSocket(config.endpoints.recommendations.ws);
            recWs.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'NEW_RECOMMENDATION') {
                        setRecommendations(prev => {
                            const filtered = prev.filter(r => r.symbol !== msg.data.symbol);
                            return [msg.data, ...filtered].slice(0, 50);
                        });
                    }
                } catch {}
            };
        } catch {}

        // Progress WebSocket
        let progressWs;
        try {
            progressWs = new WebSocket(config.endpoints.scan.progress);
            progressWs.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    setCrawlProgress(data);
                    if (data.log) {
                        setLogs(prev => [...prev, { msg: data.log, time: Date.now() }].slice(-200));
                    }
                    if (data.status === 'completed') {
                        setLogs(prev => [...prev, { msg: '✓ Scan cycle complete', time: Date.now() }]);
                        setTimeout(() => setCrawlProgress(null), 3000);
                        fetchScanConfig().then(setScanConfig).catch(() => {});
                    }
                    if (data.status === 'starting') {
                        setLogs([{ msg: '→ Initiating market scan...', time: Date.now() }]);
                    }
                } catch {}
            };
        } catch {}

        return () => {
            recWs?.readyState === WebSocket.OPEN && recWs.close();
            progressWs?.readyState === WebSocket.OPEN && progressWs.close();
        };
    }, [load]);

    const startCrawl = useCallback(async () => {
        setCrawling(true);
        setLogs(prev => [...prev, { msg: '→ Manual scan triggered...', time: Date.now() }]);
        try {
            await triggerCrawl();
            const cfg = await fetchScanConfig();
            setScanConfig(cfg);
        } catch (err) {
            setLogs(prev => [...prev, { msg: `✗ Scan failed: ${err.message}`, time: Date.now() }]);
        } finally {
            setCrawling(false);
        }
    }, []);

    const changeInterval = useCallback(async (interval) => {
        try {
            const cfg = await updateScanConfig(interval, interval > 0);
            setScanConfig(cfg);
        } catch {}
    }, []);

    return {
        recommendations, loading, error, scanConfig, crawling,
        crawlProgress, logs, startCrawl, changeInterval, refresh: load
    };
};
