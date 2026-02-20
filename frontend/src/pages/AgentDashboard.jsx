import React, { useState, useEffect, useCallback } from 'react';
import {
    Box, Typography, Container, Card, CardContent, Grid, Chip, Button, Stack,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
    LinearProgress, alpha, useTheme, Avatar, IconButton, Tooltip, Divider, Badge
} from '@mui/material';
import {
    Bot, Activity, TrendingUp, TrendingDown, ShieldCheck, Eye, RefreshCw,
    Power, PowerOff, Zap, Clock, Target, BarChart3, AlertTriangle,
    ArrowUpRight, ArrowDownRight, Cpu, Wifi, WifiOff
} from 'lucide-react';
import { fetchAgentStatus, fetchPortfolio, fetchRecommendations } from '../services/api';
import { formatINR, isBullish, getDirectionColor, getDirectionBg, getDirectionLabel, timeAgo, getPnlColor } from '../utils/formatters';

const AgentDashboard = () => {
    const _theme = useTheme();
    const [agentStatus, setAgentStatus] = useState({ status: 'online', active_monitors: 0, last_action: null, trades_today: 0, win_rate: 0 });
    const [portfolio, setPortfolio] = useState(null);
    const [recommendations, setRecommendations] = useState([]);
    const [_loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        try {
            setLoading(true);
            const [status, port, recs] = await Promise.all([
                fetchAgentStatus(),
                fetchPortfolio().catch(() => null),
                fetchRecommendations().catch(() => [])
            ]);
            setAgentStatus(status);
            setPortfolio(port);
            setRecommendations(recs);
        } catch (err) {
            console.error('Agent load error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
        const iv = setInterval(load, 10000);
        return () => clearInterval(iv);
    }, [load]);

    const isOnline = agentStatus?.status !== 'offline';
    const activeTrades = portfolio?.active_trades || [];
    const tradeHistory = portfolio?.trade_history || [];
    const unrealizedPnl = activeTrades.reduce((s, t) => s + (t.pnl || 0), 0);
    const realizedPnl = portfolio?.realized_pnl || 0;
    const _totalTrades = activeTrades.length + tradeHistory.length;
    const winTrades = tradeHistory.filter(t => (t.pnl || 0) > 0).length;
    const winRate = tradeHistory.length > 0 ? (winTrades / tradeHistory.length * 100) : 0;

    // Pending signals = recs not yet traded, HIGH conviction only (≥65%)
    const HIGH_CONVICTION_THRESHOLD = 65;
    const tradedSymbols = new Set([...activeTrades.map(t => t.symbol), ...tradeHistory.map(t => t.symbol)]);
    const pendingSignals = recommendations
        .filter(r =>
            !tradedSymbols.has(r.symbol) && (r.conviction || r.confidence || 0) >= HIGH_CONVICTION_THRESHOLD
        )
        .sort((a, b) => (b.conviction || b.confidence || 0) - (a.conviction || a.confidence || 0));

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 4 }}>
                <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Avatar sx={{ width: 48, height: 48, bgcolor: isOnline ? alpha('#10b981', 0.1) : alpha('#ef4444', 0.1), color: isOnline ? '#10b981' : '#ef4444' }}>
                            <Bot size={24} />
                        </Avatar>
                        <Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: '-0.02em' }}>Intraday Agent</Typography>
                                <Chip
                                    icon={isOnline ? <Wifi size={12} /> : <WifiOff size={12} />}
                                    label={isOnline ? 'ONLINE' : 'OFFLINE'}
                                    size="small"
                                    sx={{
                                        fontWeight: 800, fontSize: '0.6rem', height: 24,
                                        bgcolor: isOnline ? alpha('#10b981', 0.1) : alpha('#ef4444', 0.1),
                                        color: isOnline ? '#10b981' : '#ef4444',
                                        '& .MuiChip-icon': { color: 'inherit' },
                                    }}
                                />
                            </Box>
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                Autonomous trading agent monitoring intraday signals • 9:15 AM - 3:15 PM IST
                            </Typography>
                        </Box>
                    </Box>
                </Box>
                <Button variant="outlined" startIcon={<RefreshCw size={14} />} onClick={load} sx={{ borderRadius: 2, fontWeight: 600 }}>
                    Refresh
                </Button>
            </Box>

            {/* Stats */}
            <Grid container spacing={2} sx={{ mb: 4 }}>
                {[
                    { label: 'Active Positions', value: activeTrades.length, icon: <Activity size={18} />, color: '#38bdf8' },
                    { label: 'Unrealized P&L', value: formatINR(unrealizedPnl), icon: <TrendingUp size={18} />, color: unrealizedPnl >= 0 ? '#10b981' : '#ef4444' },
                    { label: 'Realized P&L', value: formatINR(realizedPnl), icon: <BarChart3 size={18} />, color: realizedPnl >= 0 ? '#10b981' : '#ef4444' },
                    { label: 'Win Rate', value: `${winRate.toFixed(0)}%`, icon: <Target size={18} />, color: '#f59e0b' },
                    { label: 'High Conv. Signals', value: pendingSignals.length, icon: <Zap size={18} />, color: '#818cf8' },
                    { label: 'Cash Balance', value: formatINR(portfolio?.cash_balance || 0, 0), icon: <ShieldCheck size={18} />, color: '#10b981' },
                ].map((item) => (
                    <Grid size={{ xs: 6, md: 2 }} key={item.label}>
                        <Card>
                            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                    <Box sx={{ color: item.color }}>{item.icon}</Box>
                                    <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.5rem', lineHeight: 1.2 }}>{item.label}</Typography>
                                </Box>
                                <Typography variant="h5" fontWeight={800} sx={{ color: item.color }}>{item.value}</Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>

            <Grid container spacing={3}>
                {/* Active Positions */}
                <Grid size={{ xs: 12, lg: 8 }}>
                    <Card>
                        <CardContent sx={{ p: 0 }}>
                            <Box sx={{ px: 3, py: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid', borderColor: 'divider' }}>
                                <Typography variant="subtitle1" fontWeight={800} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Activity size={16} /> Active Positions ({activeTrades.length})
                                </Typography>
                            </Box>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Symbol</TableCell>
                                            <TableCell>Type</TableCell>
                                            <TableCell align="right">Qty</TableCell>
                                            <TableCell align="right">Entry</TableCell>
                                            <TableCell align="right">LTP</TableCell>
                                            <TableCell align="right">P&L</TableCell>
                                            <TableCell align="right">Target</TableCell>
                                            <TableCell align="right">SL</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {activeTrades.length === 0 ? (
                                            <TableRow>
                                                <TableCell colSpan={8} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                                                    <Bot size={32} style={{ opacity: 0.2, marginBottom: 8 }} />
                                                    <Typography variant="body2">No active positions. Agent is monitoring signals...</Typography>
                                                </TableCell>
                                            </TableRow>
                                        ) : activeTrades.map((t) => (
                                            <TableRow key={t.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                                                <TableCell>
                                                    <Typography variant="body2" fontWeight={700}>{t.symbol}</Typography>
                                                    <Typography variant="caption" color="text.secondary">{new Date(t.entry_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</Typography>
                                                </TableCell>
                                                <TableCell>
                                                    <Chip label={t.type} size="small" sx={{
                                                        height: 20, fontSize: '0.6rem', fontWeight: 800,
                                                        bgcolor: t.type === 'BUY' ? alpha('#10b981', 0.1) : alpha('#ef4444', 0.1),
                                                        color: t.type === 'BUY' ? '#10b981' : '#ef4444',
                                                    }} />
                                                </TableCell>
                                                <TableCell align="right">{t.quantity}</TableCell>
                                                <TableCell align="right">{formatINR(t.entry_price)}</TableCell>
                                                <TableCell align="right">{t.current_price ? formatINR(t.current_price) : '---'}</TableCell>
                                                <TableCell align="right">
                                                    <Typography variant="body2" fontWeight={700} sx={{ color: getPnlColor(t.pnl) }}>
                                                        {(t.pnl || 0) >= 0 ? '+' : ''}{formatINR(t.pnl || 0)}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell align="right" sx={{ color: '#10b981' }}>{formatINR(t.target)}</TableCell>
                                                <TableCell align="right" sx={{ color: '#ef4444' }}>{formatINR(t.stop_loss)}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>

                    {/* Trade History */}
                    <Card sx={{ mt: 3 }}>
                        <CardContent sx={{ p: 0 }}>
                            <Box sx={{ px: 3, py: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                                <Typography variant="subtitle1" fontWeight={800} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Clock size={16} /> Trade History ({tradeHistory.length})
                                </Typography>
                            </Box>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Symbol</TableCell>
                                            <TableCell>Type</TableCell>
                                            <TableCell align="right">P&L</TableCell>
                                            <TableCell align="right">Exit Price</TableCell>
                                            <TableCell>Reason</TableCell>
                                            <TableCell>Time</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {tradeHistory.length === 0 ? (
                                            <TableRow>
                                                <TableCell colSpan={6} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                                                    No completed trades yet
                                                </TableCell>
                                            </TableRow>
                                        ) : tradeHistory.slice().reverse().map((t) => (
                                            <TableRow key={t.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                                                <TableCell><Typography variant="body2" fontWeight={700}>{t.symbol}</Typography></TableCell>
                                                <TableCell><Typography variant="body2" fontWeight={600}>{t.type}</Typography></TableCell>
                                                <TableCell align="right">
                                                    <Typography variant="body2" fontWeight={700} sx={{ color: getPnlColor(t.pnl) }}>
                                                        {(t.pnl || 0) >= 0 ? '+' : ''}{formatINR(t.pnl || 0)}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell align="right">{formatINR(t.exit_price)}</TableCell>
                                                <TableCell>
                                                    <Chip label={t.rationale_summary?.split('|').pop()?.trim() || 'Closed'} size="small"
                                                        sx={{ height: 20, fontSize: '0.6rem', fontWeight: 600 }} />
                                                </TableCell>
                                                <TableCell>
                                                    <Typography variant="caption" color="text.secondary">{t.exit_time ? new Date(t.exit_time).toLocaleString() : ''}</Typography>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Sidebar: Pending Signals */}
                <Grid size={{ xs: 12, lg: 4 }}>
                    <Card>
                        <CardContent sx={{ p: 0 }}>
                            <Box sx={{ px: 3, py: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                                <Typography variant="subtitle1" fontWeight={800} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Zap size={16} color="#f59e0b" /> High Conviction Signals ({pendingSignals.length})
                                </Typography>
                                <Typography variant="caption" color="text.secondary">Only ≥65% conviction • Sorted by strength</Typography>
                            </Box>
                            <Stack sx={{ maxHeight: 600, overflowY: 'auto' }}>
                                {pendingSignals.length === 0 ? (
                                    <Box sx={{ p: 4, textAlign: 'center' }}>
                                        <Cpu size={32} style={{ opacity: 0.2 }} />
                                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>All signals processed</Typography>
                                    </Box>
                                ) : pendingSignals.map((rec) => {
                                    const _bullish = isBullish(rec.direction);
                                    const dirColor = getDirectionColor(rec.direction);
                                    const conviction = rec.conviction || rec.confidence || 0;
                                    const convColor = conviction >= 80 ? '#10b981' : conviction >= 65 ? '#f59e0b' : '#ef4444';

                                    return (
                                        <Box key={rec.id} sx={{
                                            px: 3, py: 2, borderBottom: '1px solid', borderColor: 'divider',
                                            '&:hover': { bgcolor: 'action.hover' }, cursor: 'pointer',
                                        }}>
                                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                                    <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: dirColor }} />
                                                    <Box>
                                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                            <Typography variant="body2" fontWeight={700}>{rec.symbol}</Typography>
                                                            <Chip label={getDirectionLabel(rec.direction)} size="small"
                                                                sx={{ height: 18, fontSize: '0.55rem', fontWeight: 800, bgcolor: getDirectionBg(rec.direction), color: dirColor }} />
                                                            <Chip label={`${conviction.toFixed(0)}%`} size="small"
                                                                sx={{ height: 18, fontSize: '0.55rem', fontWeight: 800, bgcolor: alpha(convColor, 0.1), color: convColor }} />
                                                        </Box>
                                                        <Typography variant="caption" color="text.secondary">
                                                            {formatINR(rec.price || rec.entry)} • {conviction >= 80 ? 'Very High' : 'High'} conviction
                                                        </Typography>
                                                    </Box>
                                                </Box>
                                                <Box sx={{ textAlign: 'right' }}>
                                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                        {timeAgo(rec.timestamp)}
                                                    </Typography>
                                                </Box>
                                            </Box>
                                        </Box>
                                    );
                                })}
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </Container>
    );
};

export default AgentDashboard;
