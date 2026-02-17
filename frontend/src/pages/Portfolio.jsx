
import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Container, Card, CardContent,
    Button, Stack, Grid, Divider, Chip, Table, TableBody,
    TableCell, TableContainer, TableHead, TableRow, Paper, Alert,
    Dialog, DialogTitle, DialogContent, DialogActions, DialogContentText,
    IconButton, Collapse, Tabs, Tab, Tooltip, LinearProgress
} from '@mui/material';
import { Wallet, Briefcase, TrendingUp, TrendingDown, RefreshCw, History, RotateCcw, Activity, ChevronDown, ChevronUp, Zap, Eye } from 'lucide-react';
import axios from 'axios';
import { config } from '../config';
import { fetchOptionsPortfolio } from '../services/api';

const Portfolio = () => {
    const [portfolio, setPortfolio] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [resetDialogOpen, setResetDialogOpen] = useState(false);
    const [resetting, setResetting] = useState(false);
    const [optionsPortfolio, setOptionsPortfolio] = useState(null);
    const [activeTab, setActiveTab] = useState(0);
    const [expandedOptionTrade, setExpandedOptionTrade] = useState(null);

    const fetchPortfolio = async () => {
        try {
            const token = localStorage.getItem('token');
            let authHeaders = {};
            if (token) {
                authHeaders['Authorization'] = 'Bearer ' + token;
            }

            const [response, optResp] = await Promise.all([
                axios.get(config.endpoints.trading.portfolio, { headers: authHeaders }),
                fetchOptionsPortfolio().catch(() => null),
            ]);

            if (response.data) {
                setPortfolio(response.data);
            }
            if (optResp) {
                setOptionsPortfolio(optResp);
            }
        } catch (error) {
            console.error("Error fetching portfolio:", error);
            if (!portfolio) {
                setPortfolio({
                    cash_balance: 100000,
                    realized_pnl: 0,
                    active_trades: [],
                    trade_history: []
                });
            }
            setError("Trading service temporarily unavailable. Showing cached data.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchPortfolio();
        // Poll every 5 seconds for live P&L updates
        const interval = setInterval(fetchPortfolio, 5000);
        return () => clearInterval(interval);
    }, []);  // eslint-disable-line react-hooks/exhaustive-deps

    const handleResetPortfolio = async () => {
        setResetting(true);
        try {
            const token = localStorage.getItem('token');
            let authHeaders = {};
            if (token) authHeaders['Authorization'] = 'Bearer ' + token;
            await axios.post(`${config.API_BASE_URL}/trading/portfolio/reset`, {}, { headers: authHeaders });
            await fetchPortfolio();
            setResetDialogOpen(false);
            setError(null);
        } catch (err) {
            console.error('Reset failed:', err);
            setError('Failed to reset portfolio');
        } finally {
            setResetting(false);
        }
    };

    if (loading && !portfolio) {
        return (
            <Container maxWidth="lg" sx={{ py: 12, textAlign: 'center' }}>
                <Typography variant="h6" color="text.secondary">Loading Portfolio...</Typography>
            </Container>
        );
    }

    if (error && !portfolio) {
        return (
            <Container maxWidth="lg" sx={{ py: 4 }}>
                <Alert severity="error" sx={{ borderRadius: 2 }}>{error}</Alert>
            </Container>
        );
    }

    // Calculate Unrealized P&L
    const unrealizedPnl = portfolio.active_trades.reduce((acc, trade) => {
        return acc + (trade.pnl || 0);
    }, 0);

    const _totalValue = portfolio.cash_balance + unrealizedPnl;

    // Combined capital across stocks + options
    const optCapital = optionsPortfolio?.capital || 0;
    const optTotalPnl = optionsPortfolio?.total_pnl || 0;
    const combinedCapital = portfolio.cash_balance + optCapital;
    const combinedPnl = portfolio.realized_pnl + optTotalPnl;

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', mb: 4 }}>
                <Box>
                    <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: -1 }}>Paper Trading</Typography>
                    <Typography variant="subtitle1" color="text.secondary" fontWeight={500}>
                        Automated AI Execution • Stocks + Options
                    </Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                    <Stack direction="row" spacing={1} justifyContent="flex-end" sx={{ mb: 1 }}>
                        <Button
                            startIcon={<RefreshCw size={16} />}
                            onClick={fetchPortfolio}
                            variant="outlined"
                            size="small"
                        >
                            Refresh
                        </Button>
                        <Button
                            startIcon={<RotateCcw size={16} />}
                            onClick={() => setResetDialogOpen(true)}
                            variant="outlined"
                            size="small"
                            color="warning"
                        >
                            Reset
                        </Button>
                    </Stack>
                    <Typography variant="caption" color="text.secondary" display="block">Combined Capital</Typography>
                    <Typography variant="h4" fontWeight={800} color="primary.main">
                        ₹{combinedCapital.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </Typography>
                    <Typography variant="caption" color={combinedPnl >= 0 ? 'success.main' : 'error.main'} fontWeight={700}>
                        {combinedPnl >= 0 ? '+' : ''}₹{combinedPnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })} total P&L
                    </Typography>
                </Box>
            </Box>

            {/* Stats Cards - Combined */}
            <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <Wallet size={20} className="text-gray-400" />
                                <Typography variant="subtitle2" color="text.secondary" fontWeight={700}>STOCKS MARGIN</Typography>
                            </Box>
                            <Typography variant="h4" fontWeight={800}>
                                ₹{portfolio.cash_balance.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%', borderColor: unrealizedPnl >= 0 ? 'rgba(39, 201, 63, 0.3)' : 'rgba(255, 95, 86, 0.3)' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <Eye size={20} />
                                <Typography variant="subtitle2" color="text.secondary" fontWeight={700}>UNREALIZED P&L</Typography>
                            </Box>
                            <Typography variant="h4" fontWeight={800} sx={{ color: unrealizedPnl >= 0 ? 'success.main' : 'error.main' }}>
                                {unrealizedPnl >= 0 ? '+' : ''}₹{unrealizedPnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                {portfolio.active_trades.length} open position{portfolio.active_trades.length !== 1 ? 's' : ''}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <Activity size={20} />
                                <Typography variant="subtitle2" color="text.secondary" fontWeight={700}>OPTIONS CAPITAL</Typography>
                            </Box>
                            <Typography variant="h4" fontWeight={800}>
                                ₹{optCapital.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <History size={20} className="text-gray-400" />
                                <Typography variant="subtitle2" color="text.secondary" fontWeight={700}>STOCKS REALIZED P&L</Typography>
                            </Box>
                            <Typography variant="h4" fontWeight={800} sx={{ color: portfolio.realized_pnl >= 0 ? 'success.main' : 'error.main' }}>
                                {portfolio.realized_pnl >= 0 ? '+' : ''}₹{portfolio.realized_pnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 2.4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <TrendingUp size={20} />
                                <Typography variant="subtitle2" color="text.secondary" fontWeight={700}>OPTIONS P&L</Typography>
                            </Box>
                            <Typography variant="h4" fontWeight={800} sx={{ color: optTotalPnl >= 0 ? 'success.main' : 'error.main' }}>
                                {optTotalPnl >= 0 ? '+' : ''}₹{optTotalPnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Tab Switch: Stocks | Options */}
            <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ mb: 3, '& .MuiTab-root': { fontWeight: 700, textTransform: 'none' } }}>
                <Tab label={`Stocks (${portfolio.active_trades.length} active)`} icon={<Briefcase size={16} />} iconPosition="start" />
                <Tab label={`Options (${optionsPortfolio?.stats?.total_trades || 0} trades)`} icon={<Activity size={16} />} iconPosition="start" />
            </Tabs>

            {/* ── STOCKS TAB ── */}
            {activeTab === 0 && (
                <Box>
            {/* Active Trades */}
            <Typography variant="h6" fontWeight={800} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <TrendingUp size={20} /> Active Positions
            </Typography>
            <TableContainer component={Paper} variant="outlined" sx={{ mb: 6, borderRadius: 3 }}>
                <Table>
                    <TableHead sx={{ bgcolor: 'rgba(255,255,255,0.02)' }}>
                        <TableRow>
                            <TableCell><Typography variant="caption" fontWeight={700}>SYMBOL</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>TYPE</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>QTY</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>ENTRY</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>LTP</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>P&L</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>TARGET</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>SL</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>STATUS</Typography></TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {portfolio.active_trades.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={9} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                                    No active trades. Waiting for signals...
                                </TableCell>
                            </TableRow>
                        ) : (
                            portfolio.active_trades.map((trade) => (
                                <TableRow key={trade.id}>
                                    <TableCell>
                                        <Typography variant="body2" fontWeight={700}>{trade.symbol}</Typography>
                                        <Typography variant="caption" color="text.secondary">{new Date(trade.entry_time).toLocaleTimeString()}</Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Chip
                                            label={trade.type}
                                            size="small"
                                            sx={{
                                                bgcolor: trade.type === 'BUY' ? 'rgba(39, 201, 63, 0.1)' : 'rgba(255, 95, 86, 0.1)',
                                                color: trade.type === 'BUY' ? 'success.main' : 'error.main',
                                                fontWeight: 800, borderRadius: 1
                                            }}
                                        />
                                    </TableCell>
                                    <TableCell align="right">{trade.quantity}</TableCell>
                                    <TableCell align="right">₹{trade.entry_price.toFixed(2)}</TableCell>
                                    <TableCell align="right">
                                        {trade.current_price ? '₹' + trade.current_price.toFixed(2) : '-'}
                                    </TableCell>
                                    <TableCell align="right">
                                        <Typography
                                            variant="body2"
                                            fontWeight={700}
                                            sx={{ color: (trade.pnl || 0) >= 0 ? 'success.main' : 'error.main' }}
                                        >
                                            {(trade.pnl || 0) >= 0 ? '+' : ''}₹{trade.pnl?.toFixed(2) || '0.00'}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {trade.pnl_percent?.toFixed(2) || '0.00'}%
                                        </Typography>
                                    </TableCell>
                                    <TableCell align="right" sx={{ color: 'success.main' }}>₹{trade.target.toFixed(2)}</TableCell>
                                    <TableCell align="right" sx={{ color: 'error.main' }}>₹{trade.stop_loss.toFixed(2)}</TableCell>
                                    <TableCell align="right">
                                        <Chip label="OPEN" size="small" variant="outlined" sx={{ fontWeight: 700 }} />
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

            {/* Trade History */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" fontWeight={800} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <History size={20} /> Trade History
                    {portfolio.trade_history.length > 0 && (
                        <Chip label={portfolio.trade_history.length} size="small" sx={{ fontWeight: 700, ml: 1 }} />
                    )}
                </Typography>
                {portfolio.trade_history.length > 0 && (
                    <Button
                        size="small"
                        color="error"
                        variant="text"
                        onClick={async () => {
                            if (!window.confirm('Clear all trade history? This cannot be undone.')) return;
                            try {
                                const token = localStorage.getItem('token');
                                let authHeaders = {};
                                if (token) authHeaders['Authorization'] = 'Bearer ' + token;
                                await axios.post(`${config.API_BASE_URL}/trading/portfolio/clear-history`, {}, { headers: authHeaders });
                                await fetchPortfolio();
                            } catch (err) { console.error('Clear history failed:', err); }
                        }}
                        sx={{ fontSize: '0.75rem' }}
                    >
                        Clear History
                    </Button>
                )}
            </Box>
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3, overflowX: 'auto' }}>
                <Table sx={{ minWidth: 700 }}>
                    <TableHead sx={{ bgcolor: 'rgba(255,255,255,0.02)' }}>
                        <TableRow>
                            <TableCell><Typography variant="caption" fontWeight={700}>SYMBOL</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>TYPE</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>QTY</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>ENTRY</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>EXIT</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>P&L</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>EXIT REASON</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>TIME</Typography></TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {portfolio.trade_history.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={8} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                                    No completed trades yet. Trades will appear here when positions are closed via target, stop-loss, trend reversal, or EOD square-off.
                                </TableCell>
                            </TableRow>
                        ) : (
                            portfolio.trade_history.slice().reverse().map((trade) => {
                                const exitReason = trade.rationale_summary?.split('|').pop()?.trim() || 'Closed';
                                const isProfit = (trade.pnl || 0) >= 0;
                                return (
                                    <TableRow key={trade.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                                        <TableCell>
                                            <Typography variant="body2" fontWeight={700}>{trade.symbol}</Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={trade.type}
                                                size="small"
                                                sx={{
                                                    bgcolor: trade.type === 'BUY' ? 'rgba(39, 201, 63, 0.1)' : 'rgba(255, 95, 86, 0.1)',
                                                    color: trade.type === 'BUY' ? 'success.main' : 'error.main',
                                                    fontWeight: 800, borderRadius: 1
                                                }}
                                            />
                                        </TableCell>
                                        <TableCell align="right">{trade.quantity}</TableCell>
                                        <TableCell align="right">₹{trade.entry_price?.toFixed(2)}</TableCell>
                                        <TableCell align="right">₹{trade.exit_price?.toFixed(2)}</TableCell>
                                        <TableCell align="right">
                                            <Typography
                                                variant="body2"
                                                fontWeight={700}
                                                sx={{ color: isProfit ? 'success.main' : 'error.main' }}
                                            >
                                                {isProfit ? '+' : ''}₹{(trade.pnl || 0).toFixed(2)}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                {(trade.pnl_percent || 0).toFixed(2)}%
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={exitReason}
                                                size="small"
                                                variant="outlined"
                                                sx={{
                                                    borderRadius: 1,
                                                    maxWidth: 160,
                                                    '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' }
                                                }}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="caption" color="text.secondary" noWrap>
                                                {trade.entry_time ? new Date(trade.entry_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                                                {' → '}
                                                {trade.exit_time ? new Date(trade.exit_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary" display="block" noWrap>
                                                {trade.exit_time ? new Date(trade.exit_time).toLocaleDateString() : ''}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                );
                            })
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
                </Box>
            )}

            {/* ── OPTIONS TAB ── */}
            {activeTab === 1 && (
                <Box>
                    {!optionsPortfolio ? (
                        <Alert severity="info" sx={{ borderRadius: 2 }}>Options trading service is loading...</Alert>
                    ) : (
                        <>
                            {/* Options Stats */}
                            <Grid container spacing={2} sx={{ mb: 3 }}>
                                <Grid size={{ xs: 6, md: 3 }}>
                                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                                            <Typography variant="h4" fontWeight={800}>
                                                {optionsPortfolio.stats?.total_trades || 0}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary" fontWeight={700}>TOTAL TRADES</Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                                <Grid size={{ xs: 6, md: 3 }}>
                                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                                            <Typography variant="h4" fontWeight={800} color="success.main">
                                                {optionsPortfolio.stats?.wins || 0}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary" fontWeight={700}>WINS</Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                                <Grid size={{ xs: 6, md: 3 }}>
                                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                                            <Typography variant="h4" fontWeight={800} color="error.main">
                                                {optionsPortfolio.stats?.losses || 0}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary" fontWeight={700}>LOSSES</Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                                <Grid size={{ xs: 6, md: 3 }}>
                                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                                            <Typography variant="h4" fontWeight={800}
                                                color={(optionsPortfolio.stats?.win_rate || 0) >= 50 ? 'success.main' : 'error.main'}>
                                                {(optionsPortfolio.stats?.win_rate || 0).toFixed(0)}%
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary" fontWeight={700}>WIN RATE</Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                            </Grid>

                            {/* Active Options Position */}
                            {optionsPortfolio.active_trades?.length > 0 && (
                                <Box sx={{ mb: 3 }}>
                                    <Typography variant="h6" fontWeight={800} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <Zap size={20} /> Active Option Position
                                    </Typography>
                                    {optionsPortfolio.active_trades.map((t) => (
                                        <Card key={t.trade_id} variant="outlined" sx={{ borderRadius: 3, p: 2 }}>
                                            <Stack direction="row" alignItems="center" spacing={2} flexWrap="wrap">
                                                <Chip label={t.direction} size="small" sx={{
                                                    fontWeight: 800,
                                                    bgcolor: t.direction === 'CE' ? 'rgba(39, 201, 63, 0.1)' : 'rgba(255, 95, 86, 0.1)',
                                                    color: t.direction === 'CE' ? 'success.main' : 'error.main',
                                                }} />
                                                <Typography fontWeight={700}>Strike {t.strike}</Typography>
                                                <Typography variant="body2">Entry: ₹{t.entry_premium?.toFixed(2)}</Typography>
                                                <Typography variant="body2" fontWeight={700}
                                                    sx={{ color: t.ltp > t.entry_premium ? 'success.main' : t.ltp < t.entry_premium ? 'error.main' : 'text.primary' }}>
                                                    LTP: ₹{t.ltp?.toFixed(2) || '—'}
                                                </Typography>
                                                <Typography variant="body2">SL: ₹{t.sl_premium?.toFixed(2)}</Typography>
                                                <Typography variant="body2">Target: ₹{t.target_premium?.toFixed(2)}</Typography>
                                                <Typography variant="body2" color="text.secondary">
                                                    {t.quantity} qty ({t.lots} lot)
                                                </Typography>
                                                {t.unrealized_pnl != null && (
                                                    <Chip
                                                        label={`${t.unrealized_pnl >= 0 ? '+' : ''}₹${t.unrealized_pnl?.toFixed(2)} (${t.unrealized_pnl_pct?.toFixed(2) || 0}%)`}
                                                        size="small"
                                                        sx={{
                                                            fontWeight: 800,
                                                            bgcolor: t.unrealized_pnl >= 0 ? 'rgba(39, 201, 63, 0.1)' : 'rgba(255, 95, 86, 0.1)',
                                                            color: t.unrealized_pnl >= 0 ? 'success.main' : 'error.main',
                                                        }}
                                                    />
                                                )}
                                            </Stack>
                                        </Card>
                                    ))}
                                </Box>
                            )}

                            {/* Options Trade History with Indicators */}
                            <Typography variant="h6" fontWeight={800} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                <History size={20} /> Options Trade History
                                {(optionsPortfolio.trade_history || []).length > 0 && (
                                    <Chip label={(optionsPortfolio.trade_history || []).length} size="small" sx={{ fontWeight: 700, ml: 1 }} />
                                )}
                            </Typography>

                            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3 }}>
                                <Table size="small">
                                    <TableHead sx={{ bgcolor: 'rgba(255,255,255,0.02)' }}>
                                        <TableRow>
                                            <TableCell width={40} />
                                            <TableCell><Typography variant="caption" fontWeight={700}>DIRECTION</Typography></TableCell>
                                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>STRIKE</Typography></TableCell>
                                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>ENTRY</Typography></TableCell>
                                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>EXIT</Typography></TableCell>
                                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>P&L</Typography></TableCell>
                                            <TableCell align="center"><Typography variant="caption" fontWeight={700}>RESULT</Typography></TableCell>
                                            <TableCell><Typography variant="caption" fontWeight={700}>TIME</Typography></TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {(optionsPortfolio.trade_history || []).length === 0 ? (
                                            <TableRow>
                                                <TableCell colSpan={8} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                                                    No options trades yet. Trades appear here when auto-trader executes.
                                                </TableCell>
                                            </TableRow>
                                        ) : (
                                            [...(optionsPortfolio.trade_history || [])].reverse().map((trade) => {
                                                const isWin = trade.result === 'WIN';
                                                const hasIndicators = trade.indicators && Object.keys(trade.indicators).length > 0;
                                                const isExpanded = expandedOptionTrade === trade.trade_id;
                                                return (
                                                    <React.Fragment key={trade.trade_id}>
                                                        <TableRow
                                                            hover
                                                            onClick={() => hasIndicators && setExpandedOptionTrade(isExpanded ? null : trade.trade_id)}
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
                                                                <Chip label={trade.direction} size="small" sx={{
                                                                    fontWeight: 800, fontSize: '0.65rem', borderRadius: 1,
                                                                    bgcolor: trade.direction === 'CE' ? 'rgba(39, 201, 63, 0.1)' : 'rgba(255, 95, 86, 0.1)',
                                                                    color: trade.direction === 'CE' ? 'success.main' : 'error.main',
                                                                }} />
                                                            </TableCell>
                                                            <TableCell align="right">
                                                                <Typography variant="body2" fontWeight={700}>{trade.strike}</Typography>
                                                            </TableCell>
                                                            <TableCell align="right">₹{trade.entry_premium?.toFixed(2)}</TableCell>
                                                            <TableCell align="right">₹{trade.exit_premium?.toFixed(2) || '—'}</TableCell>
                                                            <TableCell align="right">
                                                                <Typography variant="body2" fontWeight={700}
                                                                    sx={{ color: isWin ? 'success.main' : 'error.main' }}>
                                                                    {isWin ? '+' : ''}₹{(trade.pnl || 0).toFixed(2)}
                                                                </Typography>
                                                                <Typography variant="caption" color="text.secondary">
                                                                    {(trade.pnl_pct || 0).toFixed(2)}%
                                                                </Typography>
                                                            </TableCell>
                                                            <TableCell align="center">
                                                                <Chip label={trade.result || 'OPEN'} size="small" sx={{
                                                                    fontWeight: 800, fontSize: '0.6rem', borderRadius: 1,
                                                                    bgcolor: isWin ? 'rgba(39, 201, 63, 0.15)' : 'rgba(255, 95, 86, 0.15)',
                                                                    color: isWin ? 'success.main' : 'error.main',
                                                                }} />
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
                                                                <TableCell colSpan={8} sx={{ p: 0 }}>
                                                                    <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                                                                        <Box sx={{ p: 2, bgcolor: 'rgba(99, 102, 241, 0.03)' }}>
                                                                            <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                                                                                <Eye size={14} /> Why This Trade Was Taken
                                                                            </Typography>
                                                                            <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb: 1 }}>
                                                                                <Chip size="small" variant="outlined"
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
                                                                                    sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                                                                                />
                                                                                <Chip size="small" variant="outlined"
                                                                                    label={`Conf: ${(trade.indicators.confidence || 0).toFixed(0)}%`}
                                                                                    color={(trade.indicators.confidence || 0) > 50 ? 'primary' : 'default'}
                                                                                    sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                                                                                />
                                                                            </Stack>
                                                                            {(trade.indicators.reasons || []).map((r, i) => (
                                                                                <Typography key={i} variant="caption" display="block" sx={{ pl: 1, lineHeight: 1.6 }}>
                                                                                    • {r}
                                                                                </Typography>
                                                                            ))}
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
                        </>
                    )}
                </Box>
            )}

            {/* Reset Confirmation Dialog */}
            <Dialog open={resetDialogOpen} onClose={() => setResetDialogOpen(false)}>
                <DialogTitle>Reset Portfolio</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        This will reset your paper trading portfolio to ₹1,00,000 and close all active trades. Your trade history will be preserved for reference. This action cannot be undone.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setResetDialogOpen(false)}>Cancel</Button>
                    <Button onClick={handleResetPortfolio} color="warning" variant="contained" disabled={resetting}>
                        {resetting ? 'Resetting...' : 'Reset Portfolio'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
};

export default Portfolio;
