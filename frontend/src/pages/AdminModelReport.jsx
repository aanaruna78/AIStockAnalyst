import React, { useEffect, useState } from 'react';
import {
    Box, Typography, Card, CardContent, Grid, Chip, Divider,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Paper, TextField, Button, Alert, Stack, CircularProgress, alpha
} from '@mui/material';
import { TrendingUp, TrendingDown, AlertTriangle, Send, BarChart3, Target, XCircle } from 'lucide-react';
import { fetchModelReport, fetchFailedTrades, submitModelFeedback } from '../services/api';

const AdminModelReport = () => {
    const [report, setReport] = useState(null);
    const [failedData, setFailedData] = useState(null);
    const [feedback, setFeedback] = useState('');
    const [feedbackStatus, setFeedbackStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const load = async () => {
            try {
                const [rep, failed] = await Promise.all([
                    fetchModelReport().catch(() => null),
                    fetchFailedTrades().catch(() => null),
                ]);
                setReport(rep);
                setFailedData(failed);
            } catch {
                setError('Failed to load model report.');
            } finally {
                setLoading(false);
            }
        };
        load();
    }, []);

    const handleFeedback = async (e) => {
        e.preventDefault();
        if (!feedback.trim()) return;
        try {
            await submitModelFeedback(feedback.trim());
            setFeedbackStatus('success');
            setFeedback('');
            setTimeout(() => setFeedbackStatus(null), 3000);
        } catch {
            setFeedbackStatus('error');
        }
    };

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress size={32} />
            </Box>
        );
    }

    const summary = report?.summary || { total_trades: 0, wins: 0, losses: 0, win_rate: 0, total_pnl: 0 };
    const stats = failedData?.stats || { total: 0, avg_loss: 0, worst_symbols: [] };

    return (
        <Box>
            {/* Section Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
                <Box sx={{
                    width: 44, height: 44, borderRadius: 2,
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                    <BarChart3 size={24} color="#fff" />
                </Box>
                <Box>
                    <Typography variant="h5" fontWeight={800} sx={{ letterSpacing: -0.5 }}>
                        Model Performance Report
                    </Typography>
                    <Typography variant="caption" color="text.secondary" fontWeight={600}>
                        {report?.date || 'Today'} — Daily win/loss analysis & feedback
                    </Typography>
                </Box>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{error}</Alert>}

            {/* Summary Stats */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid size={{ xs: 6, md: 3 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                            <Typography variant="h3" fontWeight={800}>{summary.total_trades}</Typography>
                            <Typography variant="caption" color="text.secondary" fontWeight={700}>TOTAL TRADES</Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 3 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, borderColor: (t) => alpha(t.palette.success.main, 0.3) }}>
                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                            <Stack direction="row" justifyContent="center" alignItems="center" gap={0.5}>
                                <TrendingUp size={18} color="#22c55e" />
                                <Typography variant="h3" fontWeight={800} color="success.main">{summary.wins}</Typography>
                            </Stack>
                            <Typography variant="caption" color="text.secondary" fontWeight={700}>WINS</Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 3 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, borderColor: (t) => alpha(t.palette.error.main, 0.3) }}>
                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                            <Stack direction="row" justifyContent="center" alignItems="center" gap={0.5}>
                                <TrendingDown size={18} color="#ef4444" />
                                <Typography variant="h3" fontWeight={800} color="error.main">{summary.losses}</Typography>
                            </Stack>
                            <Typography variant="caption" color="text.secondary" fontWeight={700}>LOSSES</Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 6, md: 3 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent sx={{ textAlign: 'center', py: 2 }}>
                            <Typography variant="h3" fontWeight={800}
                                color={summary.win_rate >= 50 ? 'success.main' : 'error.main'}
                            >
                                {summary.win_rate}%
                            </Typography>
                            <Typography variant="caption" color="text.secondary" fontWeight={700}>WIN RATE</Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* P&L + Failure Stats */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid size={{ xs: 12, md: 6 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent>
                            <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Target size={16} /> Today's P&L
                            </Typography>
                            <Typography variant="h4" fontWeight={800}
                                color={summary.total_pnl >= 0 ? 'success.main' : 'error.main'}
                            >
                                ₹{summary.total_pnl?.toLocaleString('en-IN') || '0'}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent>
                            <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                                <AlertTriangle size={16} /> Total Failed Trades (All Time)
                            </Typography>
                            <Typography variant="h4" fontWeight={800} color="warning.main">
                                {stats.total}
                            </Typography>
                            {stats.avg_loss ? (
                                <Typography variant="caption" color="text.secondary">
                                    Avg loss: ₹{stats.avg_loss?.toLocaleString('en-IN')}
                                </Typography>
                            ) : null}
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Worst Symbols */}
            {stats.worst_symbols?.length > 0 && (
                <Box sx={{ mb: 3 }}>
                    <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>
                        🔴 Worst Performing Symbols (by failure count)
                    </Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap">
                        {stats.worst_symbols.map(([sym, count]) => (
                            <Chip
                                key={sym}
                                label={`${sym} (${count})`}
                                size="small"
                                color="error"
                                variant="outlined"
                                sx={{ fontWeight: 700, fontSize: '0.75rem' }}
                            />
                        ))}
                    </Stack>
                </Box>
            )}

            {/* Failed Trades Table */}
            {report?.miss_trades?.length > 0 && (
                <Box sx={{ mb: 3 }}>
                    <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <XCircle size={16} /> Today's Losing Trades
                    </Typography>
                    <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3 }}>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell><Typography variant="caption" fontWeight={700}>SYMBOL</Typography></TableCell>
                                    <TableCell><Typography variant="caption" fontWeight={700}>TYPE</Typography></TableCell>
                                    <TableCell align="right"><Typography variant="caption" fontWeight={700}>ENTRY</Typography></TableCell>
                                    <TableCell align="right"><Typography variant="caption" fontWeight={700}>EXIT</Typography></TableCell>
                                    <TableCell align="right"><Typography variant="caption" fontWeight={700}>P&L</Typography></TableCell>
                                    <TableCell align="right"><Typography variant="caption" fontWeight={700}>CONVICTION</Typography></TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {report.miss_trades.map((t) => (
                                    <TableRow key={t.id}>
                                        <TableCell><Typography variant="body2" fontWeight={700}>{t.symbol}</Typography></TableCell>
                                        <TableCell>
                                            <Chip label={t.type} size="small" sx={{
                                                fontWeight: 700, fontSize: '0.65rem', borderRadius: 1,
                                                bgcolor: t.type === 'BUY' ? (th) => alpha(th.palette.success.main, 0.1) : (th) => alpha(th.palette.error.main, 0.1),
                                                color: t.type === 'BUY' ? 'success.main' : 'error.main',
                                            }} />
                                        </TableCell>
                                        <TableCell align="right"><Typography variant="body2">₹{t.entry_price?.toFixed(2)}</Typography></TableCell>
                                        <TableCell align="right"><Typography variant="body2">₹{t.exit_price?.toFixed(2)}</Typography></TableCell>
                                        <TableCell align="right">
                                            <Typography variant="body2" fontWeight={700} color="error.main">
                                                ₹{t.pnl?.toFixed(2)} ({t.pnl_percent?.toFixed(1)}%)
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="right"><Typography variant="body2">{t.conviction?.toFixed(0)}%</Typography></TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Box>
            )}

            {/* Winning Trades Table */}
            {report?.success_trades?.length > 0 && (
                <Box sx={{ mb: 3 }}>
                    <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TrendingUp size={16} /> Today's Winning Trades
                    </Typography>
                    <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3 }}>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell><Typography variant="caption" fontWeight={700}>SYMBOL</Typography></TableCell>
                                    <TableCell><Typography variant="caption" fontWeight={700}>TYPE</Typography></TableCell>
                                    <TableCell align="right"><Typography variant="caption" fontWeight={700}>ENTRY</Typography></TableCell>
                                    <TableCell align="right"><Typography variant="caption" fontWeight={700}>EXIT</Typography></TableCell>
                                    <TableCell align="right"><Typography variant="caption" fontWeight={700}>P&L</Typography></TableCell>
                                    <TableCell align="right"><Typography variant="caption" fontWeight={700}>CONVICTION</Typography></TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {report.success_trades.map((t) => (
                                    <TableRow key={t.id}>
                                        <TableCell><Typography variant="body2" fontWeight={700}>{t.symbol}</Typography></TableCell>
                                        <TableCell>
                                            <Chip label={t.type} size="small" sx={{
                                                fontWeight: 700, fontSize: '0.65rem', borderRadius: 1,
                                                bgcolor: t.type === 'BUY' ? (th) => alpha(th.palette.success.main, 0.1) : (th) => alpha(th.palette.error.main, 0.1),
                                                color: t.type === 'BUY' ? 'success.main' : 'error.main',
                                            }} />
                                        </TableCell>
                                        <TableCell align="right"><Typography variant="body2">₹{t.entry_price?.toFixed(2)}</Typography></TableCell>
                                        <TableCell align="right"><Typography variant="body2">₹{t.exit_price?.toFixed(2)}</Typography></TableCell>
                                        <TableCell align="right">
                                            <Typography variant="body2" fontWeight={700} color="success.main">
                                                +₹{t.pnl?.toFixed(2)} ({t.pnl_percent?.toFixed(1)}%)
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="right"><Typography variant="body2">{t.conviction?.toFixed(0)}%</Typography></TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Box>
            )}

            <Divider sx={{ my: 3 }} />

            {/* Feedback Form */}
            <Box>
                <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Send size={16} /> Admin Feedback — Help the model improve
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
                    Provide observations about missed opportunities, incorrect signals, or suggestions for the model.
                    This feedback is stored and used to guide future improvements.
                </Typography>

                {feedbackStatus === 'success' && (
                    <Alert severity="success" sx={{ mb: 2, borderRadius: 2 }}>Feedback submitted successfully!</Alert>
                )}
                {feedbackStatus === 'error' && (
                    <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>Failed to submit feedback.</Alert>
                )}

                <form onSubmit={handleFeedback}>
                    <TextField
                        multiline
                        rows={3}
                        fullWidth
                        variant="outlined"
                        placeholder="e.g. The model keeps shorting ITC despite strong fundamentals. Consider increasing weight on PE ratio..."
                        value={feedback}
                        onChange={(e) => setFeedback(e.target.value)}
                        sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
                    />
                    <Button
                        type="submit"
                        variant="contained"
                        disabled={!feedback.trim()}
                        sx={{ borderRadius: 2, fontWeight: 700, textTransform: 'none' }}
                        startIcon={<Send size={16} />}
                    >
                        Submit Feedback
                    </Button>
                </form>
            </Box>
        </Box>
    );
};

export default AdminModelReport;
