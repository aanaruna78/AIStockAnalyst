import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Box, Typography, Paper, Grid, Button, Chip, Table, TableBody, TableCell,
    TableContainer, TableHead, TableRow, Card, CardContent, CircularProgress,
    Alert, IconButton, Tooltip, Dialog, DialogTitle,
    DialogContent, DialogActions, alpha, useTheme
} from '@mui/material';
import {
    RefreshCw, Zap, Activity, BarChart3, Clock, RotateCcw, Radio
} from 'lucide-react';
import {
    fetchOptionsSpot, fetchOptionsChain, fetchOptionsPortfolio,
    fetchOptionsDailyStats, resetOptionsPortfolio, fetchAutoTradeStatus
} from '../services/api';

// ─── Helpers ────────────────────────────────────────────────────
const fmt = (v, d = 2) => v != null ? Number(v).toFixed(d) : '—';
const fmtINR = (v) => v != null ? `₹${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';
const pctColor = (v) => v > 0 ? 'success.main' : v < 0 ? 'error.main' : 'text.secondary';

const OptionsScalping = () => {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';
    const intervalRef = useRef(null);

    const [spot, setSpot] = useState(null);
    const [chain, setChain] = useState(null);
    const [portfolio, setPortfolio] = useState(null);
    const [stats, setStats] = useState(null);
    const [autoStatus, setAutoStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [resetDialogOpen, setResetDialogOpen] = useState(false);
    const [actionLoading, setActionLoading] = useState(null);

    // ─── Data fetching ──────────────────────────────────────────
    const loadAll = useCallback(async () => {
        try {
            setError(null);
            const [sp, ch, pf, st, at] = await Promise.all([
                fetchOptionsSpot().catch(() => null),
                fetchOptionsChain().catch(() => null),
                fetchOptionsPortfolio().catch(() => null),
                fetchOptionsDailyStats().catch(() => null),
                fetchAutoTradeStatus().catch(() => null),
            ]);
            if (sp) setSpot(sp);
            if (ch) setChain(ch);
            if (pf) setPortfolio(pf);
            if (st) setStats(st);
            if (at) setAutoStatus(at);
        } catch {
            setError('Failed to load options data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadAll();
        intervalRef.current = setInterval(loadAll, 10000);
        return () => clearInterval(intervalRef.current);
    }, [loadAll]);

    // ─── Actions ────────────────────────────────────────────────
    const handleReset = async () => {
        setActionLoading('reset');
        try {
            await resetOptionsPortfolio();
            await loadAll();
        } catch { /* handled */ }
        setActionLoading(null);
        setResetDialogOpen(false);
    };

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

    const isEnabled = autoStatus?.enabled ?? false;

    return (
        <Box sx={{ maxWidth: 1400, mx: 'auto', p: { xs: 2, md: 3 } }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box>
                    <Typography variant="h5" fontWeight={700} sx={{ fontFamily: 'Outfit' }}>
                        Nifty 50 Options Scalping
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Fully automated paper trading · Weekly options · 1-lot scalping
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <Tooltip title="Refresh">
                        <IconButton onClick={loadAll} size="small">
                            <RefreshCw size={18} />
                        </IconButton>
                    </Tooltip>
                    <Button variant="outlined" color="warning" size="small"
                        startIcon={<RotateCcw size={14} />}
                        onClick={() => setResetDialogOpen(true)}>
                        Reset
                    </Button>
                </Box>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {/* ─── Top Stats Row ─────────────────────────────────── */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card sx={cardSx} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">NIFTY 50 Spot</Typography>
                            <Typography variant="h6" fontWeight={700}>
                                {spot ? fmt(spot.spot || spot.price, 2) : '—'}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card sx={cardSx} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">Capital</Typography>
                            <Typography variant="h6" fontWeight={700}>
                                {portfolio ? fmtINR(portfolio.capital) : '—'}
                            </Typography>
                            {portfolio && (
                                <Typography variant="caption" sx={{ color: pctColor(portfolio.total_pnl) }}>
                                    {portfolio.total_pnl >= 0 ? '+' : ''}{fmtINR(portfolio.total_pnl)} Total P&L
                                </Typography>
                            )}
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card sx={{
                        ...cardSx,
                        border: portfolio?.unrealized_pnl ? `1px solid ${portfolio.unrealized_pnl >= 0 ? alpha('#10b981', 0.4) : alpha('#ef4444', 0.3)}` : cardSx.border,
                    }} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">Unrealized P&L</Typography>
                            <Typography variant="h6" fontWeight={700} sx={{ color: pctColor(portfolio?.unrealized_pnl || 0) }}>
                                {portfolio?.unrealized_pnl != null ? `${portfolio.unrealized_pnl >= 0 ? '+' : ''}${fmtINR(portfolio.unrealized_pnl)}` : '—'}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                {portfolio?.active_trades?.length || 0} open
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card sx={cardSx} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">Realized P&L</Typography>
                            <Typography variant="h6" fontWeight={700} sx={{ color: pctColor(portfolio?.realized_pnl || 0) }}>
                                {portfolio?.realized_pnl != null ? `${portfolio.realized_pnl >= 0 ? '+' : ''}${fmtINR(portfolio.realized_pnl)}` : '—'}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                closed trades
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card sx={cardSx} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">Today</Typography>
                            <Typography variant="h6" fontWeight={700}>
                                {stats ? `${stats.trades || 0} / 20` : '—'}
                            </Typography>
                            {stats?.pnl != null && (
                                <Typography variant="caption" sx={{ color: pctColor(stats.pnl) }}>
                                    {stats.pnl >= 0 ? '+' : ''}{fmtINR(stats.pnl)}
                                </Typography>
                            )}
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card sx={cardSx} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">Win Rate</Typography>
                            <Typography variant="h6" fontWeight={700}>
                                {portfolio?.stats?.win_rate != null ? `${fmt(portfolio.stats.win_rate, 1)}%` : '—'}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                {portfolio?.stats ? `${portfolio.stats.wins}W / ${portfolio.stats.losses}L` : '—'}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card sx={{
                        ...cardSx,
                        border: `1px solid ${alpha('#10b981', 0.4)}`,
                        bgcolor: alpha('#10b981', 0.06),
                    }} elevation={0}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                            <Typography variant="caption" color="text.secondary">Auto-Trade</Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Chip
                                    icon={<Radio size={12} />}
                                    label="ALWAYS ACTIVE"
                                    size="small"
                                    color="success"
                                    sx={{ fontWeight: 700 }}
                                />
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            <Grid container spacing={3}>
                {/* ─── Left Column: Auto-Trade Status + Active Position ── */}
                <Grid size={{ xs: 12, md: 5 }}>
                    {/* Auto-Trade Engine Status */}
                    <Paper sx={{ ...cardSx, p: 2, mb: 3 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                            <Typography variant="subtitle1" fontWeight={600}>
                                <Zap size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                                Auto-Trade Engine
                            </Typography>
                            {isEnabled && (
                                <Chip label="Scanning every 60s" size="small" variant="outlined" color="success"
                                    icon={<Radio size={10} />} sx={{ fontSize: '0.65rem' }} />
                            )}
                        </Box>

                        {/* Last signal */}
                        {autoStatus?.last_signal ? (
                            <Card sx={{ mb: 1.5, p: 1.5, bgcolor: isDark ? alpha('#fff', 0.02) : alpha('#000', 0.01) }}>
                                <Typography variant="caption" color="text.secondary" fontWeight={600}>Last Signal</Typography>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                                    <Chip
                                        label={autoStatus.last_signal.direction}
                                        size="small"
                                        color={autoStatus.last_signal.direction === 'CE' ? 'success' : 'error'}
                                        sx={{ fontWeight: 700 }}
                                    />
                                    <Typography variant="body2" fontWeight={600}>
                                        Strike {autoStatus.last_signal.strike} · {fmtINR(autoStatus.last_signal.entry)}
                                    </Typography>
                                    <Chip label={`${fmt(autoStatus.last_signal.confidence, 0)}%`}
                                        variant="outlined" size="small" sx={{ fontSize: '0.65rem' }} />
                                </Box>
                            </Card>
                        ) : (
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                                {isEnabled ? 'Scanning for signals...' : 'Auto-trade is paused'}
                            </Typography>
                        )}

                        {/* Activity Log */}
                        {autoStatus?.log?.length > 0 && (
                            <Box sx={{ maxHeight: 200, overflowY: 'auto' }}>
                                <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ mb: 0.5, display: 'block' }}>
                                    Activity Log
                                </Typography>
                                {autoStatus.log.slice().reverse().map((entry, i) => (
                                    <Box key={i} sx={{ display: 'flex', gap: 1, mb: 0.3, alignItems: 'center' }}>
                                        <Typography variant="caption" color="text.disabled" sx={{ fontFamily: 'monospace', minWidth: 55 }}>
                                            {entry.time}
                                        </Typography>
                                        <Chip label={entry.action} size="small" sx={{
                                            height: 18, fontSize: '0.55rem', fontWeight: 700,
                                            bgcolor: entry.action.includes('ENTRY') ? alpha('#10b981', 0.15)
                                                : entry.action.includes('CLOSE') ? alpha('#f59e0b', 0.15)
                                                : entry.action.includes('ERROR') ? alpha('#ef4444', 0.15)
                                                : alpha('#6b7280', 0.1),
                                            color: entry.action.includes('ENTRY') ? '#10b981'
                                                : entry.action.includes('CLOSE') ? '#f59e0b'
                                                : entry.action.includes('ERROR') ? '#ef4444'
                                                : 'text.secondary',
                                        }} />
                                        <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
                                            {entry.detail}
                                        </Typography>
                                    </Box>
                                ))}
                            </Box>
                        )}

                        {autoStatus?.last_scan && (
                            <Typography variant="caption" color="text.disabled" sx={{ mt: 1, display: 'block' }}>
                                Last scan: {new Date(autoStatus.last_scan).toLocaleTimeString('en-IN')}
                            </Typography>
                        )}
                    </Paper>

                    {/* Active Position */}
                    <Paper sx={{ ...cardSx, p: 2 }}>
                        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1.5 }}>
                            <Activity size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                            Active Position
                        </Typography>
                        {portfolio?.active_trades?.length > 0 ? (
                            portfolio.active_trades.map((t) => (
                                <Card key={t.trade_id} sx={{ mb: 1, p: 1.5, bgcolor: isDark ? alpha('#fff', 0.02) : alpha('#000', 0.01) }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                                        <Chip label={t.direction} size="small"
                                            color={t.direction === 'CE' ? 'success' : 'error'} sx={{ fontWeight: 700 }} />
                                        <Typography fontWeight={700}>Strike {t.strike}</Typography>
                                        {t.unrealized_pnl != null && (
                                            <Chip
                                                label={`${t.unrealized_pnl >= 0 ? '+' : ''}${fmtINR(t.unrealized_pnl)}`}
                                                size="small"
                                                sx={{
                                                    fontWeight: 700, ml: 'auto',
                                                    bgcolor: t.unrealized_pnl >= 0 ? alpha('#10b981', 0.15) : alpha('#ef4444', 0.15),
                                                    color: t.unrealized_pnl >= 0 ? '#10b981' : '#ef4444',
                                                }}
                                            />
                                        )}
                                    </Box>
                                    <Grid container spacing={1}>
                                        <Grid size={3}>
                                            <Typography variant="caption" color="text.secondary">Entry</Typography>
                                            <Typography variant="body2" fontWeight={600}>{fmtINR(t.entry_premium)}</Typography>
                                        </Grid>
                                        <Grid size={3}>
                                            <Typography variant="caption" color="text.secondary">LTP</Typography>
                                            <Typography variant="body2" fontWeight={700}
                                                sx={{ color: t.ltp > t.entry_premium ? '#10b981' : t.ltp < t.entry_premium ? '#ef4444' : 'text.primary' }}>
                                                {t.ltp ? fmtINR(t.ltp) : '—'}
                                            </Typography>
                                        </Grid>
                                        <Grid size={3}>
                                            <Typography variant="caption" color="text.secondary">SL</Typography>
                                            <Typography variant="body2" fontWeight={600} color="error.main">{fmtINR(t.sl_premium)}</Typography>
                                        </Grid>
                                        <Grid size={3}>
                                            <Typography variant="caption" color="text.secondary">Target</Typography>
                                            <Typography variant="body2" fontWeight={600} color="success.main">{fmtINR(t.target_premium)}</Typography>
                                        </Grid>
                                        <Grid size={4}>
                                            <Typography variant="caption" color="text.secondary">Qty</Typography>
                                            <Typography variant="body2">{t.quantity}</Typography>
                                        </Grid>
                                        <Grid size={4}>
                                            <Typography variant="caption" color="text.secondary">Slippage</Typography>
                                            <Typography variant="body2">{t.slippage_pct}%</Typography>
                                        </Grid>
                                        <Grid size={4}>
                                            <Typography variant="caption" color="text.secondary">P&L %</Typography>
                                            <Typography variant="body2" fontWeight={700}
                                                sx={{ color: pctColor(t.unrealized_pnl_pct || 0) }}>
                                                {t.unrealized_pnl_pct != null ? `${t.unrealized_pnl_pct >= 0 ? '+' : ''}${t.unrealized_pnl_pct}%` : '—'}
                                            </Typography>
                                        </Grid>
                                    </Grid>
                                    <Alert severity="info" variant="outlined" sx={{ mt: 1, py: 0, fontSize: '0.7rem' }}>
                                        Auto-managed — will close at SL/Target automatically
                                    </Alert>
                                </Card>
                            ))
                        ) : (
                            <Typography variant="body2" color="text.secondary">
                                No active position — waiting for next signal
                            </Typography>
                        )}
                    </Paper>
                </Grid>

                {/* ─── Right Column: Chain + Trade History ────────── */}
                <Grid size={{ xs: 12, md: 7 }}>
                    {/* Options Chain */}
                    <Paper sx={{ ...cardSx, p: 2, mb: 3 }}>
                        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1.5 }}>
                            <BarChart3 size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                            Options Chain {chain?.atm ? `(ATM: ${chain.atm})` : ''}
                        </Typography>
                        {chain?.chain?.length > 0 ? (
                            <TableContainer sx={{ maxHeight: 280 }}>
                                <Table size="small" stickyHeader>
                                    <TableHead>
                                        <TableRow>
                                            <TableCell sx={{ fontWeight: 600 }}>CE OI</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>CE Prem</TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 700, bgcolor: isDark ? alpha('#fff', 0.06) : alpha('#000', 0.04) }}>Strike</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>PE Prem</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>PE OI</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {chain.chain.map((row) => (
                                            <TableRow key={row.strike} sx={row.is_atm ? { bgcolor: isDark ? alpha('#2196f3', 0.1) : alpha('#2196f3', 0.05) } : {}}>
                                                <TableCell>{row.ce_oi ? Number(row.ce_oi).toLocaleString() : '—'}</TableCell>
                                                <TableCell>{fmtINR(row.ce_premium)}</TableCell>
                                                <TableCell align="center" sx={{ fontWeight: 700, bgcolor: isDark ? alpha('#fff', 0.06) : alpha('#000', 0.04) }}>
                                                    {row.strike}
                                                </TableCell>
                                                <TableCell>{fmtINR(row.pe_premium)}</TableCell>
                                                <TableCell>{row.pe_oi ? Number(row.pe_oi).toLocaleString() : '—'}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        ) : (
                            <Typography variant="body2" color="text.secondary">
                                Options chain unavailable — market may be closed
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
                                            <TableCell sx={{ fontWeight: 600 }}>Hold</TableCell>
                                            <TableCell sx={{ fontWeight: 600 }}>Result</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {portfolio.trade_history.slice().reverse().map((t, i) => (
                                            <TableRow key={t.trade_id || i}>
                                                <TableCell>
                                                    <Typography variant="caption">
                                                        {t.entry_time ? new Date(t.entry_time).toLocaleString('en-IN', {
                                                            hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short'
                                                        }) : '—'}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell>
                                                    <Chip label={t.direction} size="small"
                                                        color={t.direction === 'CE' ? 'success' : 'error'} sx={{ fontWeight: 600 }} />
                                                </TableCell>
                                                <TableCell>{t.strike}</TableCell>
                                                <TableCell>{fmtINR(t.entry_premium)}</TableCell>
                                                <TableCell>{fmtINR(t.exit_premium)}</TableCell>
                                                <TableCell>
                                                    <Typography variant="body2" fontWeight={600}
                                                        sx={{ color: pctColor(t.pnl) }}>
                                                        {t.pnl >= 0 ? '+' : ''}{fmtINR(t.pnl)}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell>
                                                    <Typography variant="caption">
                                                        {t.hold_duration_sec != null ? `${t.hold_duration_sec}s` : '—'}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell>
                                                    <Chip label={t.result || 'closed'} size="small" variant="outlined"
                                                        color={t.result === 'WIN' ? 'success' : t.result === 'LOSS' ? 'error' : 'default'}
                                                        sx={{ fontWeight: 600 }} />
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        ) : (
                            <Typography variant="body2" color="text.secondary">
                                No trade history yet — auto-trader will place trades during market hours
                            </Typography>
                        )}
                    </Paper>
                </Grid>
            </Grid>

            {/* Reset Dialog */}
            <Dialog open={resetDialogOpen} onClose={() => setResetDialogOpen(false)}>
                <DialogTitle>Reset Paper Trading Portfolio?</DialogTitle>
                <DialogContent>
                    <Typography>
                        This will reset capital to ₹1,00,000 and clear all trade history. This cannot be undone.
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
