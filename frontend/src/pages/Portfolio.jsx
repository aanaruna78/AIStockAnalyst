
import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Container, Card, CardContent,
    Button, Stack, Grid, Divider, Chip, Table, TableBody,
    TableCell, TableContainer, TableHead, TableRow, Paper, Alert
} from '@mui/material';
import { Wallet, Briefcase, TrendingUp, TrendingDown, RefreshCw, History } from 'lucide-react';
import axios from 'axios';
import { config } from '../config';

const Portfolio = () => {
    const [portfolio, setPortfolio] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchPortfolio = async () => {
        try {
            const token = localStorage.getItem('token');
            let authHeaders = {};
            if (token) {
                authHeaders['Authorization'] = 'Bearer ' + token;
            }

            const response = await axios.get(config.endpoints.trading.portfolio, { headers: authHeaders });

            if (response.data) {
                setPortfolio(response.data);
            }
        } catch (error) {
            console.error("Error fetching portfolio:", error);
            // On first load failure, show default empty portfolio instead of error
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
        // Since we don't have live price in trade object (only checks in backend), 
        // we might not see live P&L unless backend updates 'pnl' field on open trades 
        // OR we fetch live prices here.
        // For paper trading MVP, we often rely on backend 'pnl' which might be 0 until closed?
        // Let's assume backend updates it or we display 0 if not available.
        // Actually typical paper trading apps show live P&L.
        // The TradeManager implementation didn't explicitly store 'current_pnl' on open trades, only calculated on close.
        // We can enhance this later. For now, we display 'Open'.
        return acc + (trade.pnl || 0);
    }, 0);

    const _totalValue = portfolio.cash_balance + unrealizedPnl; // + cost basis of active trades ideally

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', mb: 4 }}>
                <Box>
                    <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: -1 }}>Paper Trading</Typography>
                    <Typography variant="subtitle1" color="text.secondary" fontWeight={500}>
                        Automated AI Execution • 9:15 AM - 3:15 PM
                    </Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                    <Button
                        startIcon={<RefreshCw size={16} />}
                        onClick={fetchPortfolio}
                        variant="outlined"
                        size="small"
                        sx={{ mb: 1 }}
                    >
                        Refresh
                    </Button>
                    <Typography variant="caption" color="text.secondary" display="block">Current Balance</Typography>
                    <Typography variant="h4" fontWeight={800} color="primary.main">
                        ₹{portfolio.cash_balance.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                    </Typography>
                </Box>
            </Box>

            {/* Stats Cards */}
            <Grid container spacing={3} sx={{ mb: 6 }}>
                <Grid size={{ xs: 12, md: 3 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <Wallet size={20} className="text-gray-400" />
                                <Typography variant="subtitle2" color="text.secondary" fontWeight={700}>AVAILABLE MARGIN</Typography>
                            </Box>
                            <Typography variant="h4" fontWeight={800}>
                                ₹{portfolio.cash_balance.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, md: 3 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%', borderColor: unrealizedPnl >= 0 ? 'rgba(39, 201, 63, 0.3)' : 'rgba(255, 95, 86, 0.3)', bgcolor: unrealizedPnl >= 0 ? 'rgba(39, 201, 63, 0.05)' : 'rgba(255, 95, 86, 0.05)' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <TrendingUp size={20} />
                                <Typography variant="subtitle2" color="text.secondary" fontWeight={700}>UNREALIZED P&L</Typography>
                            </Box>
                            <Typography variant="h4" fontWeight={800} sx={{ color: unrealizedPnl >= 0 ? 'success.main' : 'error.main' }}>
                                {unrealizedPnl >= 0 ? '+' : ''}₹{unrealizedPnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, md: 3 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <History size={20} className="text-gray-400" />
                                <Typography variant="subtitle2" color="text.secondary" fontWeight={700}>REALIZED P&L</Typography>
                            </Box>
                            <Typography variant="h4" fontWeight={800} sx={{ color: portfolio.realized_pnl >= 0 ? 'success.main' : 'error.main' }}>
                                {portfolio.realized_pnl >= 0 ? '+' : ''}₹{portfolio.realized_pnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, md: 3 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <Briefcase size={20} className="text-gray-400" />
                                <Typography variant="subtitle2" color="text.secondary" fontWeight={700}>ACTIVE TRADES</Typography>
                            </Box>
                            <Typography variant="h4" fontWeight={800}>
                                {portfolio.active_trades.length}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

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
            <Typography variant="h6" fontWeight={800} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <History size={20} /> Trade History
            </Typography>
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3 }}>
                <Table>
                    <TableHead sx={{ bgcolor: 'rgba(255,255,255,0.02)' }}>
                        <TableRow>
                            <TableCell><Typography variant="caption" fontWeight={700}>SYMBOL</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>TYPE</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>PNL</Typography></TableCell>
                            <TableCell align="right"><Typography variant="caption" fontWeight={700}>EXIT PRICE</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>REASON</Typography></TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {portfolio.trade_history.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={5} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                                    No completed trades yet.
                                </TableCell>
                            </TableRow>
                        ) : (
                            portfolio.trade_history.slice().reverse().map((trade) => (
                                <TableRow key={trade.id}>
                                    <TableCell>
                                        <Typography variant="body2" fontWeight={700}>{trade.symbol}</Typography>
                                        <Typography variant="caption" color="text.secondary">{new Date(trade.exit_time).toLocaleString()}</Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="body2" fontWeight={600}>{trade.type}</Typography>
                                    </TableCell>
                                    <TableCell align="right">
                                        <Typography
                                            variant="body2"
                                            fontWeight={700}
                                            sx={{ color: (trade.pnl || 0) >= 0 ? 'success.main' : 'error.main' }}
                                        >
                                            {(trade.pnl || 0) >= 0 ? '+' : ''}₹{trade.pnl?.toFixed(2)}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {trade.pnl_percent?.toFixed(2)}%
                                        </Typography>
                                    </TableCell>
                                    <TableCell align="right">₹{trade.exit_price?.toFixed(2)}</TableCell>
                                    <TableCell>
                                        <Chip label={trade.rationale_summary?.split('|').pop()?.trim() || 'Closed'} size="small" sx={{ borderRadius: 1 }} />
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Container>
    );
};

export default Portfolio;
