import React, { useEffect, useState } from 'react';
import {
    Box, Typography, Card, CardContent, Grid, Chip, Divider,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Paper, Alert, Stack, CircularProgress, alpha, IconButton, Collapse,
    Tooltip, Button, LinearProgress
} from '@mui/material';
import {
    TrendingUp, TrendingDown, Activity, Brain, ChevronDown, ChevronUp,
    RefreshCw, Target, Zap, BarChart3, Eye
} from 'lucide-react';
import { fetchOptionsPortfolio, fetchLearningStats, resetLearning } from '../services/api';

const AdminOptionsReport = () => {
    const [portfolio, setPortfolio] = useState(null);
    const [learning, setLearning] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [expandedTrade, setExpandedTrade] = useState(null);

    const load = async () => {
        try {
            const [port, learn] = await Promise.all([
                fetchOptionsPortfolio().catch(() => null),
                fetchLearningStats().catch(() => null),
            ]);
            setPortfolio(port);
            setLearning(learn);
        } catch {
            setError('Failed to load options data.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const handleResetLearning = async () => {
        if (!window.confirm('Reset the learning engine to default thresholds?')) return;
        try {
            await resetLearning();
            await load();
        } catch {
            setError('Failed to reset learning engine.');
        }
    };

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress size={32} />
            </Box>
        );
    }

    const stats = portfolio?.stats || {};
    const trades = portfolio?.trade_history || [];
    const adj = learning?.adjustments || {};
    const recentPerf = learning?.recent_performance || {};

    return (
        <Box>
            {/* Section Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Box sx={{
                        width: 44, height: 44, borderRadius: 2,
                        background: 'linear-gradient(135deg, #f59e0b, #ef4444)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <Activity size={24} color="#fff" />
                    </Box>
                    <Box>
                        <Typography variant="h5" fontWeight={800} sx={{ letterSpacing: -0.5 }}>
                            Options Scalping Report
                        </Typography>
                        <Typography variant="caption" color="text.secondary" fontWeight={600}>
                            Nifty 50 weekly options — Auto-trade performance & learning
                        </Typography>
                    </Box>
                </Box>
                <IconButton onClick={load} size="small" title="Refresh">
                    <RefreshCw size={18} />
                </IconButton>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{error}</Alert>}

            {/* Summary Stats */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={6} md={2.4}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                            <Typography variant="h3" fontWeight={800}>{stats.total_trades || 0}</Typography>
                            <Typography variant="caption" color="text.secondary" fontWeight={700}>TOTAL TRADES</Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={6} md={2.4}>
                    <Card variant="outlined" sx={{ borderRadius: 3, borderColor: (t) => alpha(t.palette.success.main, 0.3) }}>
                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                            <Stack direction="row" justifyContent="center" alignItems="center" gap={0.5}>
                                <TrendingUp size={18} color="#22c55e" />
                                <Typography variant="h3" fontWeight={800} color="success.main">{stats.wins || 0}</Typography>
                            </Stack>
                            <Typography variant="caption" color="text.secondary" fontWeight={700}>WINS</Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={6} md={2.4}>
                    <Card variant="outlined" sx={{ borderRadius: 3, borderColor: (t) => alpha(t.palette.error.main, 0.3) }}>
                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                            <Stack direction="row" justifyContent="center" alignItems="center" gap={0.5}>
                                <TrendingDown size={18} color="#ef4444" />
                                <Typography variant="h3" fontWeight={800} color="error.main">{stats.losses || 0}</Typography>
                            </Stack>
                            <Typography variant="caption" color="text.secondary" fontWeight={700}>LOSSES</Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={6} md={2.4}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                            <Typography variant="h3" fontWeight={800}
                                color={(stats.win_rate || 0) >= 50 ? 'success.main' : 'error.main'}
                            >
                                {(stats.win_rate || 0).toFixed(0)}%
                            </Typography>
                            <Typography variant="caption" color="text.secondary" fontWeight={700}>WIN RATE</Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={6} md={2.4}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                            <Typography variant="h3" fontWeight={800}
                                color={(portfolio?.total_pnl || 0) >= 0 ? 'success.main' : 'error.main'}
                            >
                                {(portfolio?.total_pnl || 0) >= 0 ? '+' : ''}₹{(portfolio?.total_pnl || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" fontWeight={700}>TOTAL P&L</Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Adaptive Learning Engine */}
            {learning && (
                <Card variant="outlined" sx={{ borderRadius: 3, mb: 3, borderColor: (t) => alpha(t.palette.info.main, 0.3) }}>
                    <CardContent>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                            <Typography variant="subtitle2" fontWeight={800} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Brain size={18} /> Adaptive Learning Engine — v{learning.version}
                            </Typography>
                            <Button size="small" variant="outlined" color="warning" onClick={handleResetLearning}
                                sx={{ fontSize: '0.7rem', textTransform: 'none' }}>
                                Reset to Defaults
                            </Button>
                        </Box>

                        <Grid container spacing={2}>
                            <Grid item xs={12} md={6}>
                                <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ mb: 1, display: 'block' }}>
                                    LEARNED THRESHOLDS
                                </Typography>
                                <Stack spacing={1}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <Typography variant="body2">RSI Bull Threshold</Typography>
                                        <Chip label={adj.rsi_bull_threshold || 60} size="small" sx={{ fontWeight: 700, minWidth: 50 }} />
                                    </Box>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <Typography variant="body2">RSI Bear Threshold</Typography>
                                        <Chip label={adj.rsi_bear_threshold || 40} size="small" sx={{ fontWeight: 700, minWidth: 50 }} />
                                    </Box>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <Typography variant="body2">Volume Spike Min</Typography>
                                        <Chip label={`${(adj.volume_spike_min || 1.0).toFixed(1)}x`} size="small" sx={{ fontWeight: 700, minWidth: 50 }} />
                                    </Box>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <Typography variant="body2">Confidence Threshold</Typography>
                                        <Chip label={`${adj.confidence_threshold || 30}%`} size="small" sx={{ fontWeight: 700, minWidth: 50 }} />
                                    </Box>
                                </Stack>
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ mb: 1, display: 'block' }}>
                                    LEARNING PERFORMANCE (Last 20)
                                </Typography>
                                <Box sx={{ mb: 1 }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                        <Typography variant="body2">Win Rate</Typography>
                                        <Typography variant="body2" fontWeight={700}
                                            color={(recentPerf.win_rate || 0) >= 50 ? 'success.main' : 'error.main'}>
                                            {(recentPerf.win_rate || 0).toFixed(0)}%
                                        </Typography>
                                    </Box>
                                    <LinearProgress
                                        variant="determinate"
                                        value={recentPerf.win_rate || 0}
                                        sx={{
                                            height: 8, borderRadius: 4,
                                            bgcolor: (t) => alpha(t.palette.error.main, 0.1),
                                            '& .MuiLinearProgress-bar': {
                                                bgcolor: (recentPerf.win_rate || 0) >= 50 ? 'success.main' : 'error.main',
                                                borderRadius: 4,
                                            }
                                        }}
                                    />
                                </Box>
                                <Stack spacing={0.5}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <Typography variant="body2">Trades Analysed</Typography>
                                        <Typography variant="body2" fontWeight={700}>{learning.total_analysed || 0}</Typography>
                                    </Box>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <Typography variant="body2">Recalibrations</Typography>
                                        <Typography variant="body2" fontWeight={700}>{(learning.version || 1) - 1}</Typography>
                                    </Box>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <Typography variant="body2">Signal Weights</Typography>
                                        <Typography variant="body2" fontWeight={700} sx={{ fontSize: '0.75rem' }}>
                                            EMA:{adj.ema_weight || 0.15} RSI:{adj.rsi_weight || 0.15} Vol:{adj.volume_weight || 0.10}
                                        </Typography>
                                    </Box>
                                </Stack>
                            </Grid>
                        </Grid>
                    </CardContent>
                </Card>
            )}

            {/* Options Trade History with Indicators */}
            <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                <BarChart3 size={16} /> Options Trade History
                {trades.length > 0 && <Chip label={trades.length} size="small" sx={{ fontWeight: 700, ml: 1 }} />}
            </Typography>

            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3 }}>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell width={40} />
                            <TableCell><Typography variant="caption" fontWeight={700}>TRADE ID</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>DIR</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>STRIKE</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>ENTRY</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>EXIT</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>P&L</Typography></TableCell>
                            <TableCell align="center"><Typography variant="caption" fontWeight={700}>RESULT</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>TIME</Typography></TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {trades.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={9} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                                    No options trades yet. Auto-trade will place trades during market hours.
                                </TableCell>
                            </TableRow>
                        ) : (
                            [...trades].reverse().map((trade) => {
                                const isWin = trade.result === 'WIN';
                                const hasIndicators = trade.indicators && Object.keys(trade.indicators).length > 0;
                                const isExpanded = expandedTrade === trade.trade_id;
                                return (
                                    <React.Fragment key={trade.trade_id}>
                                        <TableRow
                                            hover
                                            onClick={() => hasIndicators && setExpandedTrade(isExpanded ? null : trade.trade_id)}
                                            sx={{ cursor: hasIndicators ? 'pointer' : 'default' }}
                                        >
                                            <TableCell>
                                                {hasIndicators && (
                                                    <IconButton size="small">
                                                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                                    </IconButton>
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                                    {trade.trade_id?.slice(-8)}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={trade.direction}
                                                    size="small"
                                                    sx={{
                                                        fontWeight: 800, fontSize: '0.65rem', borderRadius: 1,
                                                        bgcolor: trade.direction === 'CE'
                                                            ? (t) => alpha(t.palette.success.main, 0.1)
                                                            : (t) => alpha(t.palette.error.main, 0.1),
                                                        color: trade.direction === 'CE' ? 'success.main' : 'error.main',
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell align="right">
                                                <Typography variant="body2" fontWeight={700}>{trade.strike}</Typography>
                                            </TableCell>
                                            <TableCell align="right">₹{trade.entry_premium?.toFixed(2)}</TableCell>
                                            <TableCell align="right">₹{trade.exit_premium?.toFixed(2) || '—'}</TableCell>
                                            <TableCell align="right">
                                                <Typography variant="body2" fontWeight={700}
                                                    color={isWin ? 'success.main' : 'error.main'}>
                                                    {isWin ? '+' : ''}₹{(trade.pnl || 0).toFixed(2)}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    {(trade.pnl_pct || 0).toFixed(2)}%
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="center">
                                                <Chip
                                                    label={trade.result || 'OPEN'}
                                                    size="small"
                                                    sx={{
                                                        fontWeight: 800, fontSize: '0.6rem', borderRadius: 1,
                                                        bgcolor: isWin
                                                            ? (t) => alpha(t.palette.success.main, 0.15)
                                                            : (t) => alpha(t.palette.error.main, 0.15),
                                                        color: isWin ? 'success.main' : 'error.main',
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="caption" color="text.secondary" noWrap>
                                                    {trade.entry_time ? new Date(trade.entry_time).toLocaleString('en-IN', {
                                                        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                                                    }) : ''}
                                                </Typography>
                                                {trade.hold_duration_sec && (
                                                    <Typography variant="caption" color="text.secondary" display="block">
                                                        Hold: {trade.hold_duration_sec < 60
                                                            ? `${trade.hold_duration_sec.toFixed(0)}s`
                                                            : `${(trade.hold_duration_sec / 60).toFixed(1)}m`}
                                                    </Typography>
                                                )}
                                            </TableCell>
                                        </TableRow>

                                        {/* Expanded Indicator Details */}
                                        {hasIndicators && (
                                            <TableRow>
                                                <TableCell colSpan={9} sx={{ p: 0 }}>
                                                    <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                                                        <Box sx={{ p: 2, bgcolor: (t) => alpha(t.palette.primary.main, 0.02) }}>
                                                            <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                                                                <Eye size={14} /> Trade Indicators
                                                            </Typography>
                                                            <Grid container spacing={2}>
                                                                <Grid item xs={12} md={6}>
                                                                    <Stack spacing={0.5}>
                                                                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                                                            <Chip size="small" variant="outlined"
                                                                                icon={<Zap size={12} />}
                                                                                label={`EMA9: ${trade.indicators.ema9?.toFixed(2) || '—'}`}
                                                                                sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                                                                            />
                                                                            <Chip size="small" variant="outlined"
                                                                                label={`VWAP: ${trade.indicators.vwap?.toFixed(2) || '—'}`}
                                                                                sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                                                                            />
                                                                            <Chip size="small" variant="outlined"
                                                                                label={`RSI(7): ${trade.indicators.rsi7?.toFixed(1) || '—'}`}
                                                                                color={trade.indicators.rsi7 > 60 ? 'success' : trade.indicators.rsi7 < 40 ? 'error' : 'default'}
                                                                                sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                                                                            />
                                                                            <Chip size="small" variant="outlined"
                                                                                label={`Vol: ${trade.indicators.volume_spike?.toFixed(1) || '—'}x`}
                                                                                color={trade.indicators.volume_spike > 1.2 ? 'success' : 'default'}
                                                                                sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                                                                            />
                                                                            <Chip size="small" variant="outlined"
                                                                                label={`OI: ${trade.indicators.oi_change_pct > 0 ? '+' : ''}${trade.indicators.oi_change_pct?.toFixed(1) || '0'}%`}
                                                                                sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                                                                            />
                                                                            <Chip size="small" variant="outlined"
                                                                                label={`Conf: ${(trade.indicators.confidence || 0).toFixed(0)}%`}
                                                                                color={(trade.indicators.confidence || 0) > 50 ? 'primary' : 'default'}
                                                                                sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                                                                            />
                                                                        </Box>
                                                                    </Stack>
                                                                </Grid>
                                                                <Grid item xs={12} md={6}>
                                                                    <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ mb: 0.5, display: 'block' }}>
                                                                        SIGNAL REASONS
                                                                    </Typography>
                                                                    {(trade.indicators.reasons || []).map((r, i) => (
                                                                        <Typography key={i} variant="caption" display="block" sx={{ pl: 1, lineHeight: 1.6 }}>
                                                                            • {r}
                                                                        </Typography>
                                                                    ))}
                                                                    {trade.slippage_pct && (
                                                                        <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                                                                            Slippage: {trade.slippage_pct}% | Latency: {trade.latency_ms}ms
                                                                        </Typography>
                                                                    )}
                                                                </Grid>
                                                            </Grid>
                                                        </Box>
                                                    </Collapse>
                                                </TableCell>
                                            </TableRow>
                                        )}
                                    </React.Fragment>
                                );
                            })
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    );
};

export default AdminOptionsReport;
