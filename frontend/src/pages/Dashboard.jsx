import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Grid, Card, CardContent, Chip, Container,
    Button, Skeleton, IconButton, Dialog, DialogTitle, DialogContent, Stack, Tooltip,
    FormControl, Select, MenuItem, InputLabel
} from '@mui/material';
import {
    ArrowUpRight, ArrowDownRight, TrendingUp, TrendingDown,
    Clock, ShieldCheck, Info, RefreshCw, Loader2
} from 'lucide-react';
import axios from 'axios';
import { config } from '../config';
import RationaleRenderer from '../components/RationaleRenderer';
import TickerBar from '../components/TickerBar';

// Mock data removed as per user request to show only real analysis
const mockFallback = [];

const LiveLogViewer = ({ logs }) => {
    const scrollRef = React.useRef(null);
    const [isMinimized, setIsMinimized] = React.useState(false);
    const [isMaximized, setIsMaximized] = React.useState(false);

    React.useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs, isMinimized, isMaximized]);

    return (
        <Card sx={{
            height: isMinimized ? 'auto' : (isMaximized ? '800px' : '580px'), // Approx 2 rows of cards
            transition: 'all 0.3s ease',
            borderRadius: 2,
            bgcolor: '#1a1b1e',
            border: '1px solid rgba(255,255,255,0.08)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
            // Remove maxHeight: 100% restriction to allow fixed height
        }}>
            {/* Mac Terminal Header - Refined with Controls */}
            <Box sx={{
                px: 2, py: 1.2,
                bgcolor: '#2c2e33',
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                cursor: 'pointer'
            }}>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <Tooltip title="Close (Disabled)">
                        <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.05)', cursor: 'not-allowed' }} />
                    </Tooltip>
                    <Tooltip title={isMinimized ? "Restore" : "Minimize"}>
                        <Box
                            onClick={(e) => { e.stopPropagation(); setIsMinimized(!isMinimized); }}
                            sx={{
                                width: 12, height: 12, borderRadius: '50%',
                                bgcolor: '#ffbd2e', cursor: 'pointer',
                                '&:hover': { transform: 'scale(1.2)', filter: 'brightness(1.2)' },
                                transition: 'all 0.2s',
                                display: 'flex', alignItems: 'center', justifyContent: 'center'
                            }}
                        />
                    </Tooltip>
                    <Tooltip title={isMaximized ? "Restore Size" : "Maximize"}>
                        <Box
                            onClick={(e) => { e.stopPropagation(); setIsMaximized(!isMaximized); setIsMinimized(false); }}
                            sx={{
                                width: 12, height: 12, borderRadius: '50%',
                                bgcolor: '#27c93f', cursor: 'pointer',
                                '&:hover': { transform: 'scale(1.2)', filter: 'brightness(1.2)' },
                                transition: 'all 0.2s',
                                display: 'flex', alignItems: 'center', justifyContent: 'center'
                            }}
                        />
                    </Tooltip>
                </Box>
                <Typography variant="caption" sx={{ ml: 1, color: 'text.secondary', fontWeight: 700, letterSpacing: 1, userSelect: 'none' }}>
                    AI SCAN VIEW {isMinimized ? '(MINIMIZED)' : (isMaximized ? '(MAXIMIZED)' : '')}
                </Typography>
            </Box>

            {/* Log Stream */}
            {!isMinimized && (
                <Box
                    ref={scrollRef}
                    sx={{
                        p: 2,
                        flexGrow: 1,
                        overflowY: 'auto',
                        fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                        fontSize: '0.75rem',
                        fontWeight: 500,
                        lineHeight: 1.6,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 0.5,
                        '&::-webkit-scrollbar': { width: '4px' },
                        '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.1)', borderRadius: 2 }
                    }}
                >
                    {logs.length === 0 ? (
                        <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic', opacity: 0.5 }}>
                            Waiting for crawl process...
                        </Typography>
                    ) : logs.map((log, i) => (
                        <Box key={i} sx={{ display: 'flex', gap: 1 }}>
                            <Typography component="span" sx={{ color: 'rgba(255,255,255,0.3)', minWidth: 65, fontSize: 'inherit', fontFamily: 'inherit' }}>
                                [{new Date(log.time).toLocaleTimeString([], { hour12: false })}]
                            </Typography>
                            <Typography component="span" sx={{
                                color: log.msg.toLowerCase().includes('error') ? '#ff5f56' :
                                    log.msg.toLowerCase().includes('success') ? '#27c93f' :
                                        log.msg.toLowerCase().includes('warning') ? '#ffbd2e' :
                                            log.msg.toLowerCase().includes('analyzing') ? '#00e5ff' : '#e0e0e0',
                                fontSize: 'inherit',
                                fontFamily: 'inherit'
                            }}>
                                {log.msg}
                            </Typography>
                        </Box>
                    ))}
                </Box>
            )}
        </Card>
    );
};

const Dashboard = () => {
    const [recommendations, setRecommendations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedRationale, setSelectedRationale] = useState(null);
    const [crawlingStatus, setCrawlingStatus] = useState(null);
    const [triggering, setTriggering] = useState(false);
    const [scanConfig, setScanConfig] = useState({ interval_minutes: 10, enabled: true, last_scan_time: null });
    const [logs, setLogs] = useState([]);

    const handleOpenRationale = (e, rec) => {
        e.stopPropagation();
        setSelectedRationale(rec);
    };

    const handleCloseRationale = () => setSelectedRationale(null);

    useEffect(() => {
        const fetchSignals = async () => {
            try {
                const token = localStorage.getItem('token');
                const storedPrefs = JSON.parse(localStorage.getItem('user_preferences') || '{}');

                const requestConfig = {
                    headers: token ? { Authorization: `Bearer ${token}` } : {},
                    params: {
                        risk: storedPrefs.risk,
                        horizon: storedPrefs.horizon,
                        sectors: (storedPrefs.sectors || []).join(',')
                    }
                };

                const [recResponse, configResponse] = await Promise.all([
                    axios.get(config.endpoints.recommendations.active, requestConfig),
                    axios.get(config.endpoints.scan.config, requestConfig)
                ]);

                if (recResponse.data && recResponse.data.length > 0) {
                    setRecommendations(recResponse.data);
                } else {
                    setRecommendations([]);
                }

                if (configResponse.data) {
                    setScanConfig(configResponse.data);
                }
            } catch (error) {
                console.error('Error fetching signals:', error);
                setRecommendations(mockFallback);
            } finally {
                setLoading(false);
            }
        };

        fetchSignals();

        // Recommendations WebSocket
        const recWs = new WebSocket(config.endpoints.recommendations.ws);
        recWs.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                if (message.type === 'NEW_RECOMMENDATION') {
                    const newRec = message.data;
                    setRecommendations(prev => {
                        const filtered = prev.filter(r => r.symbol !== newRec.symbol);
                        return [newRec, ...filtered].slice(0, 50);
                    });
                }
            } catch (err) { console.error('Error parsing Rec WS:', err); }
        };

        // Progress WebSocket
        let progressWs;
        const connectProgressWs = () => {
            progressWs = new WebSocket(config.endpoints.scan.progress);
            progressWs.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    setCrawlingStatus(data);

                    if (data.log) {
                        setLogs(prev => {
                            const newLogs = [...prev, { msg: data.log, time: Date.now() }];
                            return newLogs.length > 100 ? newLogs.slice(-100) : newLogs;
                        });
                    }

                    if (data.status === 'completed') {
                        setLogs(prev => [...prev, { msg: "Scan cycle successfully finished.", time: Date.now() }]);
                        setTimeout(() => setCrawlingStatus(null), 5000);
                        // Refresh config to update last scan time
                        axios.get(config.endpoints.scan.config).then(res => setScanConfig(res.data)).catch(console.error);
                    }
                    if (data.status === 'starting') {
                        setLogs([{ msg: "Initiating global market scan...", time: Date.now() }]);
                    }
                } catch (err) { console.error('Error parsing Progress WS:', err); }
            };
            progressWs.onclose = () => {
                // Potential auto-reconnect logic if needed
            };
        };

        connectProgressWs();

        return () => {
            if (recWs && recWs.readyState === WebSocket.OPEN) recWs.close();
            if (progressWs && progressWs.readyState === WebSocket.OPEN) progressWs.close();
        };
    }, []);

    // Safety timeout for scanning state
    useEffect(() => {
        let timeout;
        if (triggering || (crawlingStatus && crawlingStatus.status !== 'completed')) {
            timeout = setTimeout(() => {
                console.warn('Scan timeout reached. Resetting state.');
                setTriggering(false);
                setCrawlingStatus(null);
                setLogs(prev => [...prev, { msg: "WARNING: Scan timeout reached. System reset.", time: Date.now() }]);
            }, 120000); // 2 minute timeout
        }
        return () => clearTimeout(timeout);
    }, [triggering, crawlingStatus]);

    const handleTriggerCrawl = async () => {
        setTriggering(true);
        setLogs(prev => [...prev, { msg: "Manual trigger received. Connecting to ingestion cluster...", time: Date.now() }]);
        try {
            await axios.post(config.endpoints.scan.crawl, null);
            const configResp = await axios.get(config.endpoints.scan.config);
            setScanConfig(configResp.data);
        } catch (error) {
            console.error('Failed to trigger crawl:', error);
            setLogs(prev => [...prev, { msg: "ERROR: Cluster connection failed.", time: Date.now() }]);
        } finally {
            setTriggering(false);
        }
    };

    const handleIntervalChange = async (event) => {
        const newInterval = event.target.value;
        const enabled = newInterval > 0;
        try {
            const resp = await axios.post(config.endpoints.scan.config, null, {
                params: { interval: newInterval, enabled: enabled }
            });
            setScanConfig(resp.data);
        } catch (error) {
            console.error('Failed to update scan interval:', error);
        }
    };

    return (
        <Box sx={{
            bgcolor: 'background.default',
            position: 'fixed',
            top: '64px', // Offset for Navbar
            left: 0,
            right: 0,
            bottom: 0,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
        }}>
            <TickerBar />
            {/* Reduced right padding to keep sidebar close to edge */}
            <Box sx={{ flexGrow: 1, display: 'flex', overflow: 'hidden', pl: { xs: 2, md: 4, lg: 6 }, pr: 1, py: 4, gap: 4 }}>
                {/* Main Content Area: Market Signals Tiles - SCROLLABLE */}
                <Box sx={{
                    flex: '1 1 auto',
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    pr: 2,
                    '&::-webkit-scrollbar': { width: '6px' },
                }}>
                    {/* Header with Inline Controls */}
                    <Box sx={{ mb: 4, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Typography variant="h4" component="h1" fontWeight={900} sx={{ letterSpacing: -1.5, color: 'text.primary' }}>Market Signals</Typography>
                            <Chip label="LIVE" color="success" size="small" sx={{ fontWeight: 900, borderRadius: 1, fontSize: '0.65rem' }} />
                        </Box>

                        {/* Compact Controls Row */}
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <FormControl size="small" sx={{ minWidth: 155 }}>
                                <InputLabel id="scan-interval-label" sx={{ fontSize: '0.9rem' }}>Auto-Scan</InputLabel>
                                <Select
                                    labelId="scan-interval-label"
                                    value={scanConfig.interval_minutes}
                                    label="Auto-Scan"
                                    onChange={handleIntervalChange}
                                    sx={{ borderRadius: 1, fontSize: '0.6rem' }}
                                >
                                    <MenuItem value={0}>Off</MenuItem>
                                    <MenuItem value={1}>1m</MenuItem>
                                    <MenuItem value={5}>5m</MenuItem>
                                    <MenuItem value={10}>10m</MenuItem>
                                    <MenuItem value={30}>30m</MenuItem>
                                    <MenuItem value={60}>1h</MenuItem>
                                </Select>
                            </FormControl>

                            <Button
                                variant="contained"
                                size="small"
                                startIcon={triggering ? <Loader2 className="animate-spin" size={14} /> : <RefreshCw size={14} />}
                                onClick={handleTriggerCrawl}
                                disabled={triggering}
                                sx={{
                                    borderRadius: 2,
                                    fontWeight: 700,
                                    px: 2,
                                    py: 0.75,
                                    textTransform: 'none',
                                    fontSize: '0.8rem',
                                    height: 40,
                                    minWidth: 'auto',
                                    bgcolor: triggering ? 'rgba(0,184,212,0.4)' : 'primary.main',
                                    '&.Mui-disabled': { bgcolor: 'rgba(0,184,212,0.15)', color: 'rgba(255,255,255,0.5)' },
                                    '&:hover': { bgcolor: 'primary.dark' }
                                }}
                            >
                                {triggering ? 'Scanning...' : 'Scan Now'}
                            </Button>

                            {scanConfig.last_scan_time && (
                                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, opacity: 0.7, whiteSpace: 'nowrap' }}>
                                    Last: {new Date(scanConfig.last_scan_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </Typography>
                            )}
                        </Box>
                    </Box>

                    {/* Progress Bar (if scanning) */}
                    {crawlingStatus && (
                        <Box sx={{ mb: 3, p: 1.5, borderRadius: 2, bgcolor: 'rgba(0,229,255,0.05)', border: '1px solid rgba(0,229,255,0.1)' }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                <Typography variant="caption" fontWeight={800} color="primary.main">
                                    {crawlingStatus.status === 'processing'
                                        ? (crawlingStatus.symbol ? `ANALYZING ${crawlingStatus.symbol}` : 'PROCESSING...')
                                        : 'PRE-SCREENING...'}
                                </Typography>
                                <Typography variant="caption" fontWeight={900}>{crawlingStatus.current} / {crawlingStatus.total}</Typography>
                            </Box>
                            <Box sx={{ height: 3, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
                                <Box sx={{ width: `${crawlingStatus.percentage}%`, height: '100%', bgcolor: 'primary.main', transition: 'width 0.5s ease' }} />
                            </Box>
                        </Box>
                    )}

                    {/* Signal Cards Grid - 3-4 per row */}
                    <Grid container spacing={2}>
                        {loading ? (
                            [1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                                <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={i}>
                                    <Skeleton variant="rectangular" height={200} sx={{ borderRadius: 2 }} />
                                </Grid>
                            ))
                        ) : recommendations
                            .sort((a, b) => (b.conviction || b.confidence || 0) - (a.conviction || a.confidence || 0))
                            .filter(rec => (rec.conviction || rec.confidence || 0) > 0 && rec.rationale !== "AI Analysis pending...")
                            .map((rec) => (
                                <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={rec.id}>
                                    <Card sx={{
                                        height: '100%',
                                        borderRadius: 2,
                                        bgcolor: 'background.paper',
                                        border: '1px solid rgba(255,255,255,0.06)',
                                        boxShadow: '0 2px 12px rgba(0,0,0,0.15)',
                                        transition: 'all 0.3s ease',
                                        '&:hover': {
                                            transform: 'translateY(-4px)',
                                            boxShadow: '0 8px 20px rgba(0,0,0,0.3)',
                                            borderColor: 'primary.main'
                                        },
                                        overflow: 'hidden'
                                    }}>
                                        <CardContent sx={{ p: 2.5 }}>
                                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                                    <Typography variant="h6" fontWeight={900} sx={{ letterSpacing: -0.5 }}>{rec.symbol}</Typography>
                                                    <Chip
                                                        label={rec.direction === 'UP' || rec.direction === 'Strong Up' ? 'BULLISH' : 'BEARISH'}
                                                        size="small"
                                                        sx={{
                                                            fontWeight: 800,
                                                            fontSize: '0.6rem',
                                                            bgcolor: rec.direction === 'UP' || rec.direction === 'Strong Up' ? 'rgba(39, 201, 63, 0.15)' : 'rgba(255, 95, 86, 0.15)',
                                                            color: rec.direction === 'UP' || rec.direction === 'Strong Up' ? '#27c93f' : '#ff5f56',
                                                            borderRadius: 1,
                                                            height: 18
                                                        }}
                                                    />
                                                </Box>
                                                <Tooltip
                                                    title={
                                                        <Box sx={{ p: 0.5, maxWidth: 180 }}>
                                                            <Typography variant="caption" fontWeight={700} display="block" gutterBottom>AI Snippet</Typography>
                                                            <Typography
                                                                variant="caption"
                                                                sx={{ lineHeight: 1.2 }}
                                                                component="div"
                                                                dangerouslySetInnerHTML={{
                                                                    __html: rec.rationale
                                                                        ? (rec.rationale.includes('**Signal Analysis**')
                                                                            ? rec.rationale.split('**Signal Analysis**')[1]?.split('**')[0]?.trim().substring(0, 80) + '...'
                                                                            : rec.rationale.substring(0, 80) + '...')
                                                                        : 'No detailed rationale available.'
                                                                }}
                                                            />
                                                            <Typography variant="caption" color="primary.light" sx={{ mt: 1, display: 'block', fontStyle: 'italic', fontSize: '0.6rem' }}>
                                                                Click for full report
                                                            </Typography>
                                                        </Box>
                                                    }
                                                    arrow
                                                    placement="top"
                                                >
                                                    <IconButton
                                                        size="small"
                                                        onClick={(e) => handleOpenRationale(e, rec)}
                                                        sx={{ color: 'primary.main', p: 0.25 }}
                                                    >
                                                        <Info size={16} />
                                                    </IconButton>
                                                </Tooltip>
                                            </Box>

                                            <Typography variant="h5" fontWeight={900} sx={{ mb: 2, letterSpacing: -0.5 }}>₹{rec.price || rec.entry || '---'}</Typography>

                                            <Grid container spacing={1} sx={{ mb: 2 }}>
                                                <Grid size={6}>
                                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5, fontWeight: 600, fontSize: '0.65rem' }}>
                                                        {rec.direction === 'UP' || rec.direction === 'Strong Up' ? <TrendingUp size={12} /> : <TrendingDown size={12} />} TARGET
                                                    </Typography>
                                                    <Typography variant="body2" color={rec.direction === 'UP' || rec.direction === 'Strong Up' ? 'success.main' : 'error.main'} fontWeight={800}>₹{rec.target1 || rec.target}</Typography>
                                                </Grid>
                                                <Grid size={6} sx={{ textAlign: 'right' }}>
                                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, justifyContent: 'flex-end', mb: 0.5, fontWeight: 600, fontSize: '0.65rem' }}>
                                                        <ShieldCheck size={12} /> STOP LOSS
                                                    </Typography>
                                                    <Typography variant="body2" color={rec.direction === 'UP' || rec.direction === 'Strong Up' ? 'error.main' : 'success.main'} fontWeight={800}>₹{rec.sl}</Typography>
                                                </Grid>
                                            </Grid>

                                            <Box>
                                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                                    <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ fontSize: '0.6rem' }}>CONVICTION</Typography>
                                                    <Typography variant="caption" color="primary.main" fontWeight={800} sx={{ fontSize: '0.6rem' }}>{rec.conviction || rec.confidence}%</Typography>
                                                </Box>
                                                <Box sx={{ height: 4, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden', mb: 1.5 }}>
                                                    <Box sx={{
                                                        width: `${rec.conviction || rec.confidence}%`,
                                                        height: '100%',
                                                        bgcolor: 'primary.main',
                                                        boxShadow: '0 0 8px rgba(0,229,255,0.5)',
                                                        borderRadius: 2
                                                    }} />
                                                </Box>

                                                {/* Mini Score Breakdown Component Badges */}
                                                {rec.score_breakdown && (
                                                    <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
                                                        {Object.entries(rec.score_breakdown).map(([label, val]) => {
                                                            const colorMap = {
                                                                'Sentiment': '#00e5ff',   // Cyan
                                                                'Technical': '#ffbd2e',   // Orange
                                                                'AI Model': '#27c93f',    // Green
                                                                'Fundamental': '#d488ff', // Purple
                                                                'Analyst': '#ff5f56'      // Red
                                                            };
                                                            const color = colorMap[label] || 'rgba(255,255,255,0.4)';

                                                            return (
                                                                <Tooltip key={label} title={`${label}: ${val > 0 ? '+' : ''}${Math.round(val)}% ${val > 0 ? 'bullish' : val < 0 ? 'bearish' : 'neutral'}`}>
                                                                    <Chip
                                                                        label={
                                                                            <span>
                                                                                <b style={{ color: color }}>{label[0]}</b>
                                                                                <span style={{ opacity: 0.8, marginLeft: '1px', color: val > 0 ? '#27c93f' : val < 0 ? '#ff5f56' : 'inherit' }}>:{val > 0 ? '+' : ''}{Math.round(val)}%</span>
                                                                            </span>
                                                                        }
                                                                        size="small"
                                                                        sx={{
                                                                            height: 18,
                                                                            fontSize: '0.6rem',
                                                                            fontWeight: 700,
                                                                            bgcolor: `${color}10`, // 10% opacity version
                                                                            border: `1px solid ${color}30`, // 30% opacity version
                                                                            color: 'text.primary',
                                                                            px: 0,
                                                                            '& .MuiChip-label': { px: 0.5 }
                                                                        }}
                                                                    />
                                                                </Tooltip>
                                                            );
                                                        })}
                                                    </Stack>
                                                )}
                                            </Box>
                                        </CardContent>
                                    </Card>
                                </Grid>
                            ))}
                    </Grid>
                </Box>

                {/* Sidebar: Live Logs Only - FIXED */}
                <Box sx={{
                    width: { xs: '100%', lg: 420, xl: 520 },
                    flexShrink: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    // height: '100%', // Removed to allow content to dictate height up to max
                    pt: 8.5, // Approx 68px to align perfectly with the Grid tiles
                }}>
                    {/* Live Logs Terminal Widget */}
                    <Box sx={{ minHeight: 0 }}>
                        <LiveLogViewer logs={logs} />
                    </Box>
                </Box>
            </Box>

            {/* Enhanced AI Analysis Report Modal */}
            <Dialog
                open={Boolean(selectedRationale)}
                onClose={handleCloseRationale}
                maxWidth="sm"
                fullWidth
                PaperProps={{
                    sx: { borderRadius: 3, bgcolor: 'background.paper', border: 'none', boxShadow: '0 24px 48px rgba(0,0,0,0.2)' }
                }}
            >
                {selectedRationale && (
                    <>
                        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(0,0,0,0.05)', p: 3 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Box sx={{
                                    p: 1, borderRadius: 2,
                                    bgcolor: selectedRationale.direction === 'UP' || selectedRationale.direction === 'Strong Up' ? 'rgba(39, 201, 63, 0.1)' : 'rgba(255, 95, 86, 0.1)',
                                    color: selectedRationale.direction === 'UP' || selectedRationale.direction === 'Strong Up' ? '#27c93f' : '#ff5f56'
                                }}>
                                    {selectedRationale.direction === 'UP' || selectedRationale.direction === 'Strong Up' ? <TrendingUp size={28} /> : <TrendingDown size={28} />}
                                </Box>
                                <Box>
                                    <Typography variant="h5" fontWeight={800} color="text.primary">{selectedRationale.symbol}</Typography>
                                    <Typography variant="caption" color="text.secondary" fontWeight={600} letterSpacing={1}>AI STRATEGY REPORT</Typography>
                                </Box>
                            </Box>
                            <Chip
                                label={selectedRationale.conviction ? `${selectedRationale.conviction}% CONVICTION` : 'HIGH CONFIDENCE'}
                                color="primary"
                                variant="filled"
                                sx={{ fontWeight: 800, borderRadius: 1 }}
                            />
                        </DialogTitle>
                        <DialogContent sx={{ p: 3 }}>
                            {/* Primary Rationale Section */}
                            <Box sx={{ mb: 4 }}>
                                <Typography variant="subtitle2" fontWeight={800} color="primary.main" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.9rem' }}>
                                    <ShieldCheck size={18} /> WHY AI RECOMMENDS THIS?
                                </Typography>
                                <Box sx={{ p: 2.5, borderRadius: 2, bgcolor: 'rgba(0,184,212,0.05)', border: '1px solid rgba(0,184,212,0.1)' }}>
                                    <Typography component="div" variant="body1" color="text.primary" sx={{ lineHeight: 1.7 }}>
                                        <RationaleRenderer content={selectedRationale.rationale} />
                                    </Typography>
                                </Box>
                            </Box>

                            {/* Sub-Score Breakdown Section */}
                            {selectedRationale.score_breakdown && (
                                <Box sx={{ mb: 4 }}>
                                    <Typography variant="subtitle2" fontWeight={800} color="text.secondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.8rem', letterSpacing: 0.5 }}>
                                        <TrendingUp size={16} /> SUB-SCORE BREAKDOWN (WEIGHTED)
                                    </Typography>
                                    <Grid container spacing={1}>
                                        {Object.entries(selectedRationale.score_breakdown).map(([label, val]) => (
                                            <Grid key={label} size={4}>
                                                <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'background.default', border: '1px solid rgba(255,255,255,0.05)', textAlign: 'center' }}>
                                                    <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" sx={{ fontSize: '0.55rem', mb: 0.5 }}>{label.toUpperCase()}</Typography>
                                                    <Typography variant="body2" fontWeight={900} sx={{ color: val > 0 ? '#27c93f' : val < 0 ? '#ff5f56' : 'primary.main' }}>{val > 0 ? '+' : ''}{Math.round(val)}%</Typography>
                                                </Box>
                                            </Grid>
                                        ))}
                                    </Grid>
                                </Box>
                            )}

                            {/* Advanced Trade Management */}
                            <Typography variant="subtitle2" fontWeight={800} color="text.secondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.8rem', letterSpacing: 0.5 }}>
                                <TrendingUp size={16} /> ADVANCED TRADE MANAGEMENT
                            </Typography>

                            <Grid container spacing={2}>
                                {/* Extended Target */}
                                {selectedRationale.target2 && (
                                    <Grid size={6}>
                                        <Box sx={{ p: 2, borderRadius: 2, bgcolor: selectedRationale.direction === 'UP' || selectedRationale.direction === 'Strong Up' ? 'rgba(39, 201, 63, 0.05)' : 'rgba(255, 95, 86, 0.05)', border: selectedRationale.direction === 'UP' || selectedRationale.direction === 'Strong Up' ? '1px solid rgba(39, 201, 63, 0.1)' : '1px solid rgba(255, 95, 86, 0.1)' }}>
                                            <Typography variant="caption" color="text.secondary" fontWeight={700}>EXTENDED TARGET (T2)</Typography>
                                            <Typography variant="h6" sx={{ color: selectedRationale.direction === 'UP' || selectedRationale.direction === 'Strong Up' ? '#27c93f' : '#ff5f56' }} fontWeight={800}>₹{selectedRationale.target2}</Typography>
                                            <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>{selectedRationale.direction === 'UP' || selectedRationale.direction === 'Strong Up' ? 'Next resistance level' : 'Next support level'}</Typography>
                                        </Box>
                                    </Grid>
                                )}

                                {/* Trailing SL Strategy */}
                                <Grid size={selectedRationale.target2 ? 6 : 12}>
                                    <Box sx={{ p: 2, borderRadius: 2, bgcolor: 'rgba(255, 189, 46, 0.05)', border: '1px solid rgba(255, 189, 46, 0.2)' }}>
                                        <Typography variant="caption" color="text.secondary" fontWeight={700}>TRAILING STRATEGY</Typography>
                                        <Typography variant="body2" fontWeight={600} sx={{ mt: 0.5 }}>
                                            Once Target 1 (₹{selectedRationale.target1 || selectedRationale.target}) is hit, move Stop Loss to {selectedRationale.direction === 'UP' || selectedRationale.direction === 'Strong Up' ? 'Cost' : 'Entry'} (₹{selectedRationale.entry || selectedRationale.price}).
                                        </Typography>
                                    </Box>
                                </Grid>
                            </Grid>

                        </DialogContent>
                        <Box sx={{ p: 2, textAlign: 'right', borderTop: '1px solid rgba(0,0,0,0.05)' }}>
                            <Button onClick={handleCloseRationale} sx={{ fontWeight: 700, color: 'text.secondary' }}>Dismiss</Button>
                        </Box>
                    </>
                )}
            </Dialog>
        </Box>
    );
};

export default Dashboard;
