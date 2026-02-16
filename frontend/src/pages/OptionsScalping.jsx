import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Box, Typography, Paper, Grid, Button, Chip, Table, TableBody, TableCell,
    TableContainer, TableHead, TableRow, Card, CardContent, CircularProgress,
    Alert, Divider, IconButton, Tooltip, LinearProgress, Dialog, DialogTitle,
    DialogContent, DialogActions, alpha, useTheme
} from '@mui/material';
import {
    TrendingUp, TrendingDown, RefreshCw, Target, Zap, DollarSign, Activity,
    BarChart3, Clock, AlertTriangle, Play, Square, RotateCcw, ChevronUp, ChevronDown
} from 'lucide-react';
import {
    fetchOptionsSpot, fetchOptionsChain, fetchScalpSignal, fetchOptionsPortfolio,
    fetchOptionsDailyStats, placeOptionsTrade, closeOptionsTrade, resetOptionsPortfolio
} from '../services/api';

// ─── Helpers ────────────────────────────────────────────────────
const fmt = (v, d = 2) => v != null ? Number(v).toFixed(d) : '—';
const fmtINR = (v) => v != null ? `₹${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';
const pctColor = (v) => v > 0 ? 'success.main' : v < 0 ? 'error.main' : 'text.secondary';

const OptionsScalping = () => {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';
    const intervalRef = useRef(null);

    // state
    const [spot, setSpot] = useState(null);
    const [chain, setChain] = useState(null);
    const [signal, setSignal] = useState(null);
    const [portfolio, setPortfolio] = useState(null);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [signalLoading, setSignalLoading] = useState(false);
    const [error, setError] = useState(null);
    const [resetDialogOpen, setResetDialogOpen] = useState(false);
    const [actionLoading, setActionLoading] = useState(null);

    // ─── Data fetching ──────────────────────────────────────────
    const loadAll = useCallback(async () => {
        try {
            setError(null);
            const [sp, ch, pf, st] = await Promise.all([
                fetchOptionsSpot().catch(() => null),
                fetchOptionsChain().catch(() => null),
                fetchOptionsPortfolio().catch(() => null),
                fetchOptionsDailyStats().catch(() => null),
            ]);
            if (sp) setSpot(sp);
            if (ch) setChain(ch);
            if (pf) setPortfolio(pf);
            if (st) setStats(st);
        } catch {
            setError('Failed to load options data');
        } finally {
            setLoading(false);
        }
    }, []);

    const loadSignal = useCallback(async () => {
        setSignalLoading(true);
        try {
            const sig = await fetchScalpSignal();
            setSignal(sig);
        } catch {
            setSignal(null);
        } finally {
            setSignalLoading(false);
        }
    }, []);

    useEffect(() => {
        loadAll();
        loadSignal();
        intervalRef.current = setInterval(() => {
            loadAll();
        }, 15000);
        return () => clearInterval(intervalRef.current);
    }, [loadAll, loadSignal]);

    // ─── Actions ────────────────────────────────────────────────
    const handlePlaceTrade = async () => {
        if (!signal || signal.signal === 'NO_TRADE') return;
        setActionLoading('place');
        try {
            await placeOptionsTrade({
                direction: signal.signal,
                strike: signal.strike,
                entry_price: signal.entry,
                confidence: signal.confidence,
            });
            await loadAll();
        } catch { /* handled by API interceptor */ }
        setActionLoading(null);
    };

    const handleCloseTrade = async (tradeId) => {
        setActionLoading(tradeId);
        try {
            await closeOptionsTrade(tradeId);
            await loadAll();
        } catch { /* handled */ }
        setActionLoading(null);
    };

    const handleReset = async () => {
        setActionLoading('reset');
        try {
            await resetOptionsPortfolio();
            await loadAll();
        } catch { /* handled */ }
        setActionLoading(null);
        setResetDialogOpen(false);
    };

    // ─── Loading / Error ────────────────────────────────────────
    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    const cardSx = {
        bgcolor: isDark ? alpha('#fff', 0.04) : alpha('#000', 0.02),
        border: `1px solid ${isDark ? alpha('#fff', 0.08) : alpha('#000', 0.08)}`,
        borderRadius: 2,
    };

    return (
        <Box sx={{ maxWidth: 1400, mx: 'auto', p: { xs: 2, md: 3 } }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box>
                    <Typography variant="h5" fontWeight={700} sx={{ fontFamily: 'Outfit' }}>
                        Nifty 50 Options Scalping
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Paper trading · Weekly options · 1-lot scalping
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <Tooltip title="Refresh">
                        <IconButton onClick={() => { loadAll(); loadSignal(); }} size="small">
                            <RefreshCw size={18} />
                        </IconButton>
                    </Tooltip>
                    <Button
                        variant="outlined" color="warning" size="small"
                        startIcon={<RotateCcw size={14} />}
                        onClick={() => setResetDialogOpen(true)}
                    >
                        Reset
                    </Button>
                </Box>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {/* ─── Top Stats Row ─────────────────────────────────── */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
                {/* Nifty Spot */}
                <Grid item xs={6} md={3}>
                    <Card sx={cardSx} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">NIFTY 50 Spot</Typography>
                            <Typography variant="h6" fontWeight={700}>
                                {spot ? fmt(spot.price, 2) : '—'}
                            </Typography>
                            {spot?.change != null && (
                                <Typography variant="caption" sx={{ color: pctColor(spot.change) }}>
                                    {spot.change > 0 ? '+' : ''}{fmt(spot.change, 2)}%
                                </Typography>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                {/* Capital */}
                <Grid item xs={6} md={3}>
                    <Card sx={cardSx} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">Capital</Typography>
                            <Typography variant="h6" fontWeight={700}>
                                {portfolio ? fmtINR(portfolio.capital) : '—'}
                            </Typography>
                            {portfolio && (
                                <Typography variant="caption" sx={{ color: pctColor(portfolio.capital - 100000) }}>
                                    {portfolio.capital >= 100000 ? '+' : ''}{fmtINR(portfolio.capital - 100000)} P&L
                                </Typography>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                {/* Today's Trades */}
                <Grid item xs={6} md={3}>
                    <Card sx={cardSx} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">Today's Trades</Typography>
                            <Typography variant="h6" fontWeight={700}>
                                {stats ? `${stats.trades_today || 0} / 20` : '—'}
                            </Typography>
                            {stats?.today_pnl != null && (
                                <Typography variant="caption" sx={{ color: pctColor(stats.today_pnl) }}>
                                    {stats.today_pnl >= 0 ? '+' : ''}{fmtINR(stats.today_pnl)} today
                                </Typography>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                {/* Win Rate */}
                <Grid item xs={6} md={3}>
                    <Card sx={cardSx} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">Win Rate</Typography>
                            <Typography variant="h6" fontWeight={700}>
                                {stats?.win_rate != null ? `${fmt(stats.win_rate, 1)}%` : '—'}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                {stats ? `${stats.wins || 0}W / ${stats.losses || 0}L` : '—'}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            <Grid container spacing={3}>
                {/* ─── Left Column: Signal + Trade Panel ──────────── */}
                <Grid item xs={12} md={5}>
                    {/* Signal Card */}
                    <Paper sx={{ ...cardSx, p: 2, mb: 3 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                            <Typography variant="subtitle1" fontWeight={600}>
                                <Zap size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                                Scalp Signal
                            </Typography>
                            <Button size="small" onClick={loadSignal} disabled={signalLoading}
                                startIcon={signalLoading ? <CircularProgress size={14} /> : <RefreshCw size={14} />}>
                                Scan
                            </Button>
                        </Box>

                        {signalLoading && <LinearProgress sx={{ mb: 1 }} />}

                        {signal ? (
                            <>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                    <Chip
                                        label={signal.signal}
                                        color={signal.signal === 'CE' ? 'success' : signal.signal === 'PE' ? 'error' : 'default'}
                                        size="medium" sx={{ fontWeight: 700, fontSize: '1rem', px: 1 }}
                                    />
                                    {signal.confidence != null && (
                                        <Chip label={`${fmt(signal.confidence, 1)}% conf`}
                                            variant="outlined" size="small" />
                                    )}
                                </Box>

                                {signal.signal !== 'NO_TRADE' && (
                                    <Grid container spacing={1} sx={{ mb: 2 }}>
                                        <Grid item xs={4}>
                                            <Typography variant="caption" color="text.secondary">Strike</Typography>
                                            <Typography fontWeight={600}>{signal.strike}</Typography>
                                        </Grid>
                                        <Grid item xs={4}>
                                            <Typography variant="caption" color="text.secondary">Entry</Typography>
                                            <Typography fontWeight={600}>{fmtINR(signal.entry)}</Typography>
                                        </Grid>
                                        <Grid item xs={4}>
                                            <Typography variant="caption" color="text.secondary">Lot Size</Typography>
                                            <Typography fontWeight={600}>65</Typography>
                                        </Grid>
                                        <Grid item xs={4}>
                                            <Typography variant="caption" color="text.secondary">SL</Typography>
                                            <Typography fontWeight={600} color="error.main">{fmtINR(signal.sl)}</Typography>
                                        </Grid>
                                        <Grid item xs={4}>
                                            <Typography variant="caption" color="text.secondary">Target</Typography>
                                            <Typography fontWeight={600} color="success.main">{fmtINR(signal.target)}</Typography>
                                        </Grid>
                                        <Grid item xs={4}>
                                            <Typography variant="caption" color="text.secondary">Risk:Reward</Typography>
                                            <Typography fontWeight={600}>1:2</Typography>
                                        </Grid>
                                    </Grid>
                                )}

                                {/* Indicators */}
                                {signal.indicators && (
                                    <Box sx={{ mb: 2 }}>
                                        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                                            Indicators
                                        </Typography>
                                        <Grid container spacing={0.5}>
                                            {Object.entries(signal.indicators).map(([k, v]) => (
                                                <Grid item xs={6} key={k}>
                                                    <Typography variant="caption">
                                                        {k.replace(/_/g, ' ')}: <strong>{typeof v === 'number' ? fmt(v, 2) : String(v)}</strong>
                                                    </Typography>
                                                </Grid>
                                            ))}
                                        </Grid>
                                    </Box>
                                )}

                                {signal.signal !== 'NO_TRADE' && (
                                    <Button
                                        variant="contained" fullWidth
                                        color={signal.signal === 'CE' ? 'success' : 'error'}
                                        startIcon={actionLoading === 'place' ? <CircularProgress size={16} color="inherit" /> : <Play size={16} />}
                                        disabled={actionLoading === 'place'}
                                        onClick={handlePlaceTrade}
                                        sx={{ fontWeight: 700 }}
                                    >
                                        Place {signal.signal} Trade · Strike {signal.strike}
                                    </Button>
                                )}

                                {signal.signal === 'NO_TRADE' && (
                                    <Alert severity="info" variant="outlined">
                                        No scalping signal — conditions not met. Will re-scan.
                                    </Alert>
                                )}
                            </>
                        ) : (
                            <Typography color="text.secondary" variant="body2">
                                Click Scan to generate a scalping signal
                            </Typography>
                        )}
                    </Paper>

                    {/* Active Trades */}
                    <Paper sx={{ ...cardSx, p: 2 }}>
                        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1.5 }}>
                            <Activity size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                            Active Trades
                        </Typography>
                        {portfolio?.active_trades?.length > 0 ? (
                            portfolio.active_trades.map((t) => (
                                <Card key={t.id} sx={{ mb: 1, p: 1.5, bgcolor: isDark ? alpha('#fff', 0.02) : alpha('#000', 0.01) }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <Box>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                <Chip label={t.direction} size="small"
                                                    color={t.direction === 'CE' ? 'success' : 'error'} />
                                                <Typography fontWeight={600}>
                                                    {t.strike} · {fmtINR(t.entry_price)}
                                                </Typography>
                                            </Box>
                                            <Typography variant="caption" color="text.secondary">
                                                Qty: {t.quantity} · SL: {fmtINR(t.sl)} · Tgt: {fmtINR(t.target)}
                                            </Typography>
                                        </Box>
                                        <Button
                                            variant="outlined" color="warning" size="small"
                                            disabled={actionLoading === t.id}
                                            startIcon={actionLoading === t.id ? <CircularProgress size={12} /> : <Square size={14} />}
                                            onClick={() => handleCloseTrade(t.id)}
                                        >
                                            Close
                                        </Button>
                                    </Box>
                                </Card>
                            ))
                        ) : (
                            <Typography variant="body2" color="text.secondary">
                                No active trades
                            </Typography>
                        )}
                    </Paper>
                </Grid>

                {/* ─── Right Column: Options Chain + History ──────── */}
                <Grid item xs={12} md={7}>
                    {/* Options Chain */}
                    <Paper sx={{ ...cardSx, p: 2, mb: 3 }}>
                        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1.5 }}>
                            <BarChart3 size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                            Options Chain {chain?.atm_strike ? `(ATM: ${chain.atm_strike})` : ''}
                        </Typography>
                        {chain?.strikes?.length > 0 ? (
                            <TableContainer sx={{ maxHeight: 320 }}>
                                <Table size="small" stickyHeader>
                                    <TableHead>
                                        <TableRow>
                                            <TableCell sx={{ fontWeight: 600 }}>CE OI</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>CE Bid</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>CE Ask</TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 700, bgcolor: isDark ? alpha('#fff', 0.06) : alpha('#000', 0.04) }}>Strike</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>PE Bid</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>PE Ask</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>PE OI</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {chain.strikes.map((row) => {
                                            const isATM = row.strike === chain.atm_strike;
                                            return (
                                                <TableRow key={row.strike} sx={isATM ? { bgcolor: isDark ? alpha('#2196f3', 0.1) : alpha('#2196f3', 0.05) } : {}}>
                                                    <TableCell>{row.ce_oi ? Number(row.ce_oi).toLocaleString() : '—'}</TableCell>
                                                    <TableCell>{fmt(row.ce_bid)}</TableCell>
                                                    <TableCell>{fmt(row.ce_ask)}</TableCell>
                                                    <TableCell align="center" sx={{ fontWeight: 700, bgcolor: isDark ? alpha('#fff', 0.06) : alpha('#000', 0.04) }}>
                                                        {row.strike}
                                                    </TableCell>
                                                    <TableCell>{fmt(row.pe_bid)}</TableCell>
                                                    <TableCell>{fmt(row.pe_ask)}</TableCell>
                                                    <TableCell>{row.pe_oi ? Number(row.pe_oi).toLocaleString() : '—'}</TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        ) : (
                            <Typography variant="body2" color="text.secondary">
                                Options chain data unavailable — market may be closed
                            </Typography>
                        )}
                    </Paper>

                    {/* Trade History */}
                    <Paper sx={{ ...cardSx, p: 2 }}>
                        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1.5 }}>
                            <Clock size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                            Trade History
                        </Typography>
                        {portfolio?.trade_history?.length > 0 ? (
                            <TableContainer sx={{ maxHeight: 360 }}>
                                <Table size="small" stickyHeader>
                                    <TableHead>
                                        <TableRow>
                                            <TableCell sx={{ fontWeight: 600 }}>Time</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>Dir</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>Strike</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>Entry</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>Exit</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>P&L</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {portfolio.trade_history.slice().reverse().map((t, i) => (
                                            <TableRow key={t.id || i}>
                                                <TableCell>
                                                    <Typography variant="caption">
                                                        {t.entry_time ? new Date(t.entry_time).toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' }) : '—'}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell>
                                                    <Chip label={t.direction} size="small"
                                                        color={t.direction === 'CE' ? 'success' : 'error'} />
                                                </TableCell>
                                                <TableCell>{t.strike}</TableCell>
                                                <TableCell>{fmtINR(t.entry_price)}</TableCell>
                                                <TableCell>{fmtINR(t.exit_price)}</TableCell>
                                                <TableCell>
                                                    <Typography variant="body2" fontWeight={600}
                                                        sx={{ color: pctColor(t.pnl) }}>
                                                        {t.pnl >= 0 ? '+' : ''}{fmtINR(t.pnl)}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell>
                                                    <Chip label={t.result || 'closed'} size="small" variant="outlined"
                                                        color={t.result === 'WIN' ? 'success' : t.result === 'LOSS' ? 'error' : 'default'} />
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        ) : (
                            <Typography variant="body2" color="text.secondary">
                                No trade history yet — place your first scalp trade
                            </Typography>
                        )}
                    </Paper>
                </Grid>
            </Grid>

            {/* Reset Confirmation Dialog */}
            <Dialog open={resetDialogOpen} onClose={() => setResetDialogOpen(false)}>
                <DialogTitle>Reset Paper Trading Portfolio?</DialogTitle>
                <DialogContent>
                    <Typography>
                        This will reset capital to ₹1,00,000 and clear all trade history. This action cannot be undone.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setResetDialogOpen(false)}>Cancel</Button>
                    <Button onClick={handleReset} color="error" variant="contained"
                        disabled={actionLoading === 'reset'}>
                        {actionLoading === 'reset' ? 'Resetting...' : 'Reset Portfolio'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default OptionsScalping;
