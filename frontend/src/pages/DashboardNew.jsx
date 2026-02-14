import React, { useState, useMemo } from 'react';
import {
    Box, Typography, Grid, Card, CardContent, Chip, Button, Skeleton,
    IconButton, Dialog, DialogTitle, DialogContent, Stack, Tooltip,
    FormControl, Select, MenuItem, InputLabel, LinearProgress, Tabs, Tab,
    TextField, InputAdornment, Badge, Divider, Avatar, alpha, useTheme, Fab
} from '@mui/material';
import {
    ArrowUpRight, ArrowDownRight, TrendingUp, TrendingDown, Clock, ShieldCheck,
    Info, RefreshCw, Loader2, Search, Filter, ChevronRight, Activity,
    Target, AlertTriangle, BarChart3, Zap, Eye, BookOpen, Terminal, X
} from 'lucide-react';
import { useRecommendations } from '../hooks/useRecommendations';
import RationaleRenderer from '../components/RationaleRenderer';
import TickerBar from '../components/TickerBar';
import { formatINR, formatPercent, isBullish, getDirectionColor, getDirectionBg, getDirectionLabel, getConvictionLevel, SCORE_COLORS, timeAgo } from '../utils/formatters';

// ─── Live Log Terminal ──────────────────────────────────────────
const LiveLogTerminal = ({ logs }) => {
    const scrollRef = React.useRef(null);
    const [minimized, setMinimized] = React.useState(false);
    const [maximized, setMaximized] = React.useState(false);

    React.useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [logs, minimized, maximized]);

    return (
        <Card sx={{
            height: minimized ? 'auto' : (maximized ? '80vh' : '540px'),
            transition: 'all 0.3s ease',
            bgcolor: '#0d1117',
            border: '1px solid rgba(255,255,255,0.06)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
        }}>
            <Box sx={{
                px: 2, py: 1,
                bgcolor: '#161b22',
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                borderBottom: '1px solid rgba(255,255,255,0.04)',
            }}>
                <Box sx={{ display: 'flex', gap: 0.75 }}>
                    <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.04)' }} />
                    <Tooltip title={minimized ? 'Restore' : 'Minimize'}>
                        <Box onClick={() => setMinimized(!minimized)} sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#f59e0b', cursor: 'pointer', '&:hover': { filter: 'brightness(1.2)' } }} />
                    </Tooltip>
                    <Tooltip title={maximized ? 'Restore' : 'Maximize'}>
                        <Box onClick={() => { setMaximized(!maximized); setMinimized(false); }} sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#10b981', cursor: 'pointer', '&:hover': { filter: 'brightness(1.2)' } }} />
                    </Tooltip>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 1 }}>
                    <Activity size={12} color="#10b981" />
                    <Typography variant="overline" sx={{ color: '#64748b', fontSize: '0.6rem' }}>
                        SCAN CONSOLE {minimized ? '• MINIMIZED' : ''}
                    </Typography>
                </Box>
                <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: logs.length > 0 ? '#10b981' : '#475569', animation: logs.length > 0 ? 'pulse 2s infinite' : 'none', '@keyframes pulse': { '0%, 100%': { opacity: 1 }, '50%': { opacity: 0.4 } } }} />
                    <Typography variant="caption" sx={{ color: '#475569', fontSize: '0.6rem' }}>{logs.length}</Typography>
                </Box>
            </Box>
            {!minimized && (
                <Box ref={scrollRef} sx={{
                    p: 1.5, flexGrow: 1, overflowY: 'auto',
                    fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
                    fontSize: '0.7rem', lineHeight: 1.7,
                    '&::-webkit-scrollbar': { width: '4px' },
                    '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.08)', borderRadius: 4 },
                }}>
                    {logs.length === 0 ? (
                        <Typography sx={{ color: '#475569', fontStyle: 'italic', fontFamily: 'inherit', fontSize: 'inherit' }}>
                            $ waiting for scan process...
                        </Typography>
                    ) : logs.map((log, i) => (
                        <Box key={i} sx={{ display: 'flex', gap: 1, py: 0.2 }}>
                            <Typography component="span" sx={{ color: '#475569', minWidth: 60, fontFamily: 'inherit', fontSize: 'inherit' }}>
                                {new Date(log.time).toLocaleTimeString([], { hour12: false })}
                            </Typography>
                            <Typography component="span" sx={{
                                fontFamily: 'inherit', fontSize: 'inherit',
                                color: log.msg.includes('✗') || log.msg.toLowerCase().includes('error') ? '#ef4444' :
                                    log.msg.includes('✓') || log.msg.toLowerCase().includes('success') ? '#10b981' :
                                    log.msg.includes('→') || log.msg.toLowerCase().includes('analyzing') ? '#38bdf8' :
                                    log.msg.toLowerCase().includes('warning') ? '#f59e0b' : '#94a3b8',
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

// ─── Signal Card ────────────────────────────────────────────────
const SignalCard = ({ rec, onViewReport }) => {
    const theme = useTheme();
    const bullish = isBullish(rec.direction);
    const dirColor = getDirectionColor(rec.direction);
    const conviction = rec.conviction || rec.confidence || 0;
    const convLevel = getConvictionLevel(conviction);

    return (
        <Card sx={{
            height: '100%',
            position: 'relative',
            overflow: 'visible',
            '&:hover': {
                transform: 'translateY(-2px)',
                boxShadow: `0 8px 24px ${alpha(dirColor, 0.15)}`,
                borderColor: alpha(dirColor, 0.3),
            },
            '&::before': {
                content: '""',
                position: 'absolute',
                top: 0, left: 0, right: 0,
                height: 3,
                borderRadius: '16px 16px 0 0',
                background: `linear-gradient(90deg, ${dirColor}, ${alpha(dirColor, 0.4)})`,
            },
        }}>
            <CardContent sx={{ p: 2.5, display: 'flex', flexDirection: 'column', height: '100%' }}>
                {/* Header */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                    <Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                            <Typography variant="h6" fontWeight={800} sx={{ letterSpacing: '-0.02em' }}>{rec.symbol}</Typography>
                            <Chip
                                icon={bullish ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                                label={getDirectionLabel(rec.direction)}
                                size="small"
                                sx={{
                                    fontWeight: 800,
                                    fontSize: '0.6rem',
                                    height: 22,
                                    bgcolor: getDirectionBg(rec.direction),
                                    color: dirColor,
                                    border: `1px solid ${alpha(dirColor, 0.2)}`,
                                    '& .MuiChip-icon': { color: dirColor, ml: 0.5 },
                                }}
                            />
                        </Box>
                        {rec.timestamp && (
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Clock size={10} /> {timeAgo(rec.timestamp)}
                            </Typography>
                        )}
                    </Box>
                    <Tooltip title="View AI Report">
                        <IconButton size="small" onClick={(e) => { e.stopPropagation(); onViewReport(rec); }}
                            sx={{ color: 'primary.main', bgcolor: alpha(theme.palette.primary.main, 0.08), '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.15) } }}>
                            <BookOpen size={14} />
                        </IconButton>
                    </Tooltip>
                </Box>

                {/* Price */}
                <Typography variant="h5" fontWeight={800} sx={{ mb: 2, letterSpacing: '-0.02em' }}>
                    {formatINR(rec.price || rec.entry, 2)}
                </Typography>

                {/* Targets */}
                <Grid container spacing={1} sx={{ mb: 2 }}>
                    <Grid size={6}>
                        <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: alpha(bullish ? '#10b981' : '#ef4444', 0.06), border: `1px solid ${alpha(bullish ? '#10b981' : '#ef4444', 0.1)}` }}>
                            <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.55rem', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Target size={10} /> TARGET
                            </Typography>
                            <Typography variant="body2" fontWeight={800} sx={{ color: bullish ? '#10b981' : '#ef4444' }}>
                                {formatINR(rec.target1 || rec.target, 2)}
                            </Typography>
                        </Box>
                    </Grid>
                    <Grid size={6}>
                        <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: alpha(bullish ? '#ef4444' : '#10b981', 0.06), border: `1px solid ${alpha(bullish ? '#ef4444' : '#10b981', 0.1)}` }}>
                            <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.55rem', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <ShieldCheck size={10} /> STOP LOSS
                            </Typography>
                            <Typography variant="body2" fontWeight={800} sx={{ color: bullish ? '#ef4444' : '#10b981' }}>
                                {formatINR(rec.sl, 2)}
                            </Typography>
                        </Box>
                    </Grid>
                </Grid>

                {/* Conviction */}
                <Box sx={{ mt: 'auto' }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                        <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.55rem' }}>CONVICTION</Typography>
                        <Chip label={`${conviction.toFixed(1)}% • ${convLevel.label}`} size="small"
                            sx={{ height: 18, fontSize: '0.6rem', fontWeight: 800, color: convLevel.color, bgcolor: alpha(convLevel.color, 0.1), border: `1px solid ${alpha(convLevel.color, 0.2)}` }} />
                    </Box>
                    <LinearProgress
                        variant="determinate"
                        value={Math.min(conviction, 100)}
                        sx={{
                            height: 4, borderRadius: 2,
                            bgcolor: alpha(dirColor, 0.08),
                            '& .MuiLinearProgress-bar': { bgcolor: dirColor, borderRadius: 2 },
                            mb: 1.5,
                        }}
                    />

                    {/* Sub-scores */}
                    {rec.score_breakdown && (
                        <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
                            {Object.entries(rec.score_breakdown).map(([label, val]) => {
                                const color = SCORE_COLORS[label] || '#94a3b8';
                                return (
                                    <Tooltip key={label} title={`${label}: ${val > 0 ? '+' : ''}${Math.round(val)}%`}>
                                        <Chip size="small"
                                            label={<span><b style={{ color }}>{label[0]}</b><span style={{ color: val > 0 ? '#10b981' : val < 0 ? '#ef4444' : '#94a3b8', marginLeft: 2 }}>{val > 0 ? '+' : ''}{Math.round(val)}</span></span>}
                                            sx={{ height: 20, fontSize: '0.6rem', fontWeight: 700, bgcolor: alpha(color, 0.08), border: `1px solid ${alpha(color, 0.15)}`, '& .MuiChip-label': { px: 0.75 } }}
                                        />
                                    </Tooltip>
                                );
                            })}
                        </Stack>
                    )}
                </Box>
            </CardContent>
        </Card>
    );
};

// ─── Stats Bar ──────────────────────────────────────────────────
const StatsBar = ({ recommendations }) => {
    const stats = useMemo(() => {
        const longs = recommendations.filter(r => isBullish(r.direction));
        const shorts = recommendations.filter(r => !isBullish(r.direction));
        const avgConv = recommendations.length > 0
            ? recommendations.reduce((s, r) => s + (r.conviction || r.confidence || 0), 0) / recommendations.length
            : 0;
        return { total: recommendations.length, longs: longs.length, shorts: shorts.length, avgConv };
    }, [recommendations]);

    const items = [
        { label: 'Total Signals', value: stats.total, icon: <Activity size={16} />, color: '#38bdf8' },
        { label: 'Long', value: stats.longs, icon: <ArrowUpRight size={16} />, color: '#10b981' },
        { label: 'Short', value: stats.shorts, icon: <ArrowDownRight size={16} />, color: '#ef4444' },
        { label: 'Avg Conviction', value: `${stats.avgConv.toFixed(1)}%`, icon: <BarChart3 size={16} />, color: '#f59e0b' },
    ];

    return (
        <Grid container spacing={2} sx={{ mb: 3 }}>
            {items.map((item) => (
                <Grid size={{ xs: 6, md: 3 }} key={item.label}>
                    <Box sx={{
                        p: 2, borderRadius: 3,
                        bgcolor: 'background.paper',
                        border: '1px solid', borderColor: 'divider',
                        display: 'flex', alignItems: 'center', gap: 2,
                    }}>
                        <Avatar sx={{ width: 40, height: 40, bgcolor: alpha(item.color, 0.1), color: item.color }}>
                            {item.icon}
                        </Avatar>
                        <Box>
                            <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.55rem', lineHeight: 1.2 }}>{item.label}</Typography>
                            <Typography variant="h5" fontWeight={800}>{item.value}</Typography>
                        </Box>
                    </Box>
                </Grid>
            ))}
        </Grid>
    );
};

// ─── Main Dashboard ─────────────────────────────────────────────
const Dashboard = () => {
    const {
        recommendations, loading, scanConfig, crawling,
        crawlProgress, logs, startCrawl, changeInterval
    } = useRecommendations();

    const [selectedRec, setSelectedRec] = useState(null);
    const [filterTab, setFilterTab] = useState('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [scanLogOpen, setScanLogOpen] = useState(false);
    const recs = Array.isArray(recommendations) ? recommendations : [];

    const filteredRecs = useMemo(() => {
        let filtered = recs
            .filter(r => (r.conviction || r.confidence || 0) >= 20 && r.rationale !== 'AI Analysis pending...')
            .sort((a, b) => (b.conviction || b.confidence || 0) - (a.conviction || a.confidence || 0));

        if (filterTab === 'long') filtered = filtered.filter(r => isBullish(r.direction));
        if (filterTab === 'short') filtered = filtered.filter(r => !isBullish(r.direction));

        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter(r => r.symbol?.toLowerCase().includes(q));
        }

        return filtered;
    }, [recs, filterTab, searchQuery]);

    return (
        <Box sx={{ bgcolor: 'background.default', position: 'fixed', top: 64, left: 0, right: 0, bottom: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <TickerBar />
            <Box sx={{ flexGrow: 1, display: 'flex', overflow: 'hidden', px: { xs: 2, md: 3, lg: 4 }, py: 3, gap: 3 }}>
                {/* Main Content */}
                <Box sx={{
                    flex: '1 1 auto', overflowY: 'auto', overflowX: 'hidden', pr: 1,
                    '&::-webkit-scrollbar': { width: '4px' },
                    '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.08)', borderRadius: 4 },
                }}>
                    {/* Header Row */}
                    <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: '-0.02em' }}>Market Signals</Typography>
                            <Chip icon={<Zap size={12} />} label="LIVE" color="success" size="small" sx={{ fontWeight: 800, fontSize: '0.6rem', height: 24 }} />
                        </Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                            <FormControl size="small" sx={{ minWidth: 120 }}>
                                <InputLabel sx={{ fontSize: '0.8rem' }}>Auto-Scan</InputLabel>
                                <Select value={scanConfig?.interval_minutes ?? 10} label="Auto-Scan" onChange={(e) => changeInterval(e.target.value)} sx={{ borderRadius: 2, fontSize: '0.75rem' }}>
                                    <MenuItem value={0}>Off</MenuItem>
                                    <MenuItem value={1}>1 min</MenuItem>
                                    <MenuItem value={5}>5 min</MenuItem>
                                    <MenuItem value={10}>10 min</MenuItem>
                                    <MenuItem value={30}>30 min</MenuItem>
                                    <MenuItem value={60}>1 hour</MenuItem>
                                </Select>
                            </FormControl>
                            <Button variant="contained" size="small" startIcon={crawling ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                                onClick={startCrawl} disabled={crawling}
                                sx={{ borderRadius: 2, fontWeight: 700, px: 2.5, height: 40, minWidth: 110 }}>
                                {crawling ? 'Scanning...' : 'Scan Now'}
                            </Button>
                            {scanConfig.last_scan_time && (
                                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <Clock size={11} /> {new Date(scanConfig.last_scan_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </Typography>
                            )}
                        </Box>
                    </Box>

                    {/* Scan Progress */}
                    {crawlProgress && (
                        <Box sx={{ mb: 3, p: 2, borderRadius: 3, bgcolor: alpha('#38bdf8', 0.04), border: `1px solid ${alpha('#38bdf8', 0.1)}` }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                <Typography variant="overline" color="primary.main" sx={{ fontSize: '0.6rem', fontWeight: 800 }}>
                                    {crawlProgress.status === 'processing' ? `Analyzing ${crawlProgress.symbol || '...'}` : 'Pre-screening...'}
                                </Typography>
                                <Typography variant="caption" fontWeight={800}>{crawlProgress.current}/{crawlProgress.total}</Typography>
                            </Box>
                            <LinearProgress variant="determinate" value={crawlProgress.percentage || 0} sx={{ '& .MuiLinearProgress-bar': { bgcolor: 'primary.main' } }} />
                        </Box>
                    )}

                    {/* Stats */}
                    {!loading && <StatsBar recommendations={recs.filter(r => (r.conviction || r.confidence || 0) > 0)} />}

                    {/* Filters */}
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2, gap: 2 }}>
                        <Tabs value={filterTab} onChange={(_, v) => setFilterTab(v)}
                            sx={{ minHeight: 36, '& .MuiTab-root': { minHeight: 36, py: 0.5, fontSize: '0.8rem' } }}>
                            <Tab value="all" label={`All (${recs.filter(r => (r.conviction || r.confidence || 0) > 0).length})`} />
                            <Tab value="long" label={`Long (${recs.filter(r => isBullish(r.direction)).length})`} sx={{ color: '#10b981' }} />
                            <Tab value="short" label={`Short (${recs.filter(r => !isBullish(r.direction)).length})`} sx={{ color: '#ef4444' }} />
                        </Tabs>
                        <TextField size="small" placeholder="Search symbol..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                            slotProps={{ input: { startAdornment: <InputAdornment position="start"><Search size={14} color="#64748b" /></InputAdornment> } }}
                            sx={{ width: 200, '& .MuiOutlinedInput-root': { borderRadius: 2, fontSize: '0.8rem' } }} />
                    </Box>

                    {/* Signal Cards Grid */}
                    <Grid container spacing={2}>
                        {loading ? (
                            [1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                                <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={i}>
                                    <Skeleton variant="rectangular" height={280} sx={{ borderRadius: 4 }} />
                                </Grid>
                            ))
                        ) : filteredRecs.length === 0 ? (
                            <Grid size={12}>
                                <Box sx={{ textAlign: 'center', py: 8, color: 'text.secondary' }}>
                                    <BarChart3 size={48} strokeWidth={1} style={{ opacity: 0.3, marginBottom: 16 }} />
                                    <Typography variant="h6" fontWeight={600} color="text.secondary">No signals match your criteria</Typography>
                                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                                        Try adjusting your filters or run a new scan
                                    </Typography>
                                </Box>
                            </Grid>
                        ) : filteredRecs.map((rec) => (
                            <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={rec.id}>
                                <SignalCard rec={rec} onViewReport={setSelectedRec} />
                            </Grid>
                        ))}
                    </Grid>
                </Box>
            </Box>

            {/* Floating Scan Console Button */}
            <Tooltip title="Scan Console">
                <Fab
                    size="medium"
                    onClick={() => setScanLogOpen(true)}
                    sx={{
                        position: 'fixed',
                        bottom: 24,
                        right: 24,
                        bgcolor: '#161b22',
                        color: '#10b981',
                        border: '1px solid rgba(255,255,255,0.08)',
                        '&:hover': { bgcolor: '#1c2333' },
                        zIndex: 1200,
                    }}
                >
                    <Badge
                        badgeContent={logs.length > 0 ? logs.length : null}
                        color="success"
                        max={99}
                        sx={{ '& .MuiBadge-badge': { fontSize: '0.6rem', minWidth: 16, height: 16 } }}
                    >
                        <Terminal size={20} />
                    </Badge>
                </Fab>
            </Tooltip>

            {/* Scan Console Dialog */}
            <Dialog open={scanLogOpen} onClose={() => setScanLogOpen(false)} maxWidth="md" fullWidth
                PaperProps={{ sx: { bgcolor: '#0d1117', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 3 } }}>
                <LiveLogTerminal logs={logs} />
            </Dialog>

            {/* AI Analysis Report Dialog */}
            <Dialog open={Boolean(selectedRec)} onClose={() => setSelectedRec(null)} maxWidth="sm" fullWidth>
                {selectedRec && (
                    <>
                        <DialogTitle sx={{ p: 3, borderBottom: '1px solid', borderColor: 'divider' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <Avatar sx={{ width: 44, height: 44, bgcolor: getDirectionBg(selectedRec.direction), color: getDirectionColor(selectedRec.direction) }}>
                                        {isBullish(selectedRec.direction) ? <TrendingUp size={22} /> : <TrendingDown size={22} />}
                                    </Avatar>
                                    <Box>
                                        <Typography variant="h5" fontWeight={800}>{selectedRec.symbol}</Typography>
                                        <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.6rem' }}>AI STRATEGY REPORT</Typography>
                                    </Box>
                                </Box>
                                <Chip label={`${(selectedRec.conviction || selectedRec.confidence || 0).toFixed(1)}%`} color="primary" sx={{ fontWeight: 800, borderRadius: 2 }} />
                            </Box>
                        </DialogTitle>
                        <DialogContent sx={{ p: 3 }}>
                            {/* Rationale */}
                            <Box sx={{ mb: 3 }}>
                                <Typography variant="subtitle2" fontWeight={800} color="primary.main" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Zap size={16} /> AI ANALYSIS
                                </Typography>
                                <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: alpha('#38bdf8', 0.04), border: `1px solid ${alpha('#38bdf8', 0.08)}` }}>
                                    <RationaleRenderer content={selectedRec.rationale} />
                                </Box>
                            </Box>

                            {/* Score Breakdown */}
                            {selectedRec.score_breakdown && (
                                <Box sx={{ mb: 3 }}>
                                    <Typography variant="subtitle2" fontWeight={800} color="text.secondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.75rem' }}>
                                        <BarChart3 size={14} /> SCORE BREAKDOWN
                                    </Typography>
                                    <Grid container spacing={1}>
                                        {Object.entries(selectedRec.score_breakdown).map(([label, val]) => (
                                            <Grid size={4} key={label}>
                                                <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'background.default', border: '1px solid', borderColor: 'divider', textAlign: 'center' }}>
                                                    <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.5rem' }}>{label}</Typography>
                                                    <Typography variant="body2" fontWeight={800} sx={{ color: val > 0 ? '#10b981' : val < 0 ? '#ef4444' : 'text.secondary' }}>
                                                        {val > 0 ? '+' : ''}{Math.round(val)}%
                                                    </Typography>
                                                </Box>
                                            </Grid>
                                        ))}
                                    </Grid>
                                </Box>
                            )}

                            {/* Trade Levels */}
                            <Typography variant="subtitle2" fontWeight={800} color="text.secondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.75rem' }}>
                                <Target size={14} /> TRADE MANAGEMENT
                            </Typography>
                            <Grid container spacing={2}>
                                {selectedRec.target2 && (
                                    <Grid size={6}>
                                        <Box sx={{ p: 2, borderRadius: 3, bgcolor: getDirectionBg(selectedRec.direction), border: `1px solid ${alpha(getDirectionColor(selectedRec.direction), 0.15)}` }}>
                                            <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.55rem' }}>EXTENDED TARGET (T2)</Typography>
                                            <Typography variant="h6" fontWeight={800} sx={{ color: getDirectionColor(selectedRec.direction) }}>
                                                {formatINR(selectedRec.target2)}
                                            </Typography>
                                        </Box>
                                    </Grid>
                                )}
                                <Grid size={selectedRec.target2 ? 6 : 12}>
                                    <Box sx={{ p: 2, borderRadius: 3, bgcolor: alpha('#f59e0b', 0.04), border: `1px solid ${alpha('#f59e0b', 0.15)}` }}>
                                        <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.55rem' }}>TRAILING STRATEGY</Typography>
                                        <Typography variant="body2" fontWeight={600} sx={{ mt: 0.5 }}>
                                            Move SL to entry ({formatINR(selectedRec.entry || selectedRec.price)}) after T1 hit
                                        </Typography>
                                    </Box>
                                </Grid>
                            </Grid>
                        </DialogContent>
                        <Box sx={{ p: 2, textAlign: 'right', borderTop: '1px solid', borderColor: 'divider' }}>
                            <Button onClick={() => setSelectedRec(null)} sx={{ fontWeight: 700, color: 'text.secondary' }}>Dismiss</Button>
                        </Box>
                    </>
                )}
            </Dialog>
        </Box>
    );
};

export default Dashboard;
