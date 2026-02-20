import { useState, useEffect, useMemo } from 'react';
import {
    Box, Typography, Paper, Grid, Card, CardContent, Chip, Table, TableBody,
    TableCell, TableContainer, TableHead, TableRow, CircularProgress, Alert,
    Button, ButtonGroup, TextField, IconButton, Tooltip, alpha, useTheme, Stack,
    Divider
} from '@mui/material';
import { CalendarDays, Filter, RefreshCw, TrendingUp, TrendingDown, BarChart3, Target, Clock } from 'lucide-react';
import { fetchTradeReport } from '../services/api';

// ─── Date helpers ───────────────────────────────────────────────
const toDateStr = (d) => d.toISOString().slice(0, 10);
const today = () => toDateStr(new Date());
const daysAgo = (n) => {
    const d = new Date();
    d.setDate(d.getDate() - n);
    return toDateStr(d);
};
const startOfWeek = () => {
    const d = new Date();
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    d.setDate(diff);
    return toDateStr(d);
};
const startOfMonth = () => {
    const d = new Date();
    d.setDate(1);
    return toDateStr(d);
};

const PRESETS = [
    { label: 'Today', start: today, end: today },
    { label: '7 Days', start: () => daysAgo(7), end: today },
    { label: 'This Week', start: startOfWeek, end: today },
    { label: 'This Month', start: startOfMonth, end: today },
    { label: '30 Days', start: () => daysAgo(30), end: today },
    { label: 'All Time', start: () => '', end: () => '' },
];

// ─── Formatting ─────────────────────────────────────────────────
const fmtINR = (v) => v != null ? `₹${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';
const pctColor = (v, theme) => v > 0 ? theme.palette.success.main : v < 0 ? theme.palette.error.main : theme.palette.text.secondary;

export default function TradeReports() {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';

    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(true);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [activePreset, setActivePreset] = useState('All Time');
    const [error, setError] = useState('');

    const loadReport = async (start, end) => {
        setLoading(true);
        setError('');
        try {
            const data = await fetchTradeReport(start || null, end || null);
            setReport(data);
        } catch {
            setError('Failed to load trade report');
        }
        setLoading(false);
    };

    useEffect(() => {
        // Initial load — loading is already `true` from default state
        fetchTradeReport(null, null)
            .then(data => setReport(data))
            .catch(() => setError('Failed to load trade report'))
            .finally(() => setLoading(false));
    }, []);

    const handlePreset = (preset) => {
        const s = preset.start();
        const e = preset.end();
        setStartDate(s);
        setEndDate(e);
        setActivePreset(preset.label);
        loadReport(s, e);
    };

    const handleCustomApply = () => {
        setActivePreset('');
        loadReport(startDate, endDate);
    };

    const cardSx = useMemo(() => ({
        bgcolor: isDark ? alpha('#fff', 0.04) : alpha('#000', 0.02),
        border: `1px solid ${isDark ? alpha('#fff', 0.08) : alpha('#000', 0.08)}`,
        borderRadius: 3,
    }), [isDark]);

    const stats = report || {};
    const trades = report?.trades || [];

    return (
        <Box sx={{ maxWidth: 1400, mx: 'auto', p: { xs: 2, md: 3 } }}>
            {/* ─── Header ─────────────────────────────────────── */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box>
                    <Typography variant="h5" fontWeight={700} sx={{ fontFamily: 'Outfit' }}>
                        Trade Performance Report
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Analyse trade history, P&L, and win rates across time periods
                    </Typography>
                </Box>
                <Tooltip title="Refresh">
                    <IconButton onClick={() => loadReport(startDate, endDate)} size="small">
                        <RefreshCw size={18} />
                    </IconButton>
                </Tooltip>
            </Box>

            {/* ─── Date Controls ──────────────────────────────── */}
            <Paper sx={{ ...cardSx, p: 2.5, mb: 3 }} elevation={0}>
                <Stack spacing={2}>
                    {/* Preset buttons */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
                        <CalendarDays size={18} style={{ color: theme.palette.text.secondary, flexShrink: 0 }} />
                        <Typography variant="body2" fontWeight={600} color="text.secondary" sx={{ mr: 0.5 }}>
                            Period:
                        </Typography>
                        <ButtonGroup size="small" variant="outlined" sx={{
                            '& .MuiButton-root': {
                                textTransform: 'none',
                                fontWeight: 600,
                                fontSize: '0.75rem',
                                borderRadius: '8px !important',
                                px: 1.5,
                                borderColor: isDark ? alpha('#fff', 0.12) : alpha('#000', 0.15),
                            },
                        }}>
                            {PRESETS.map((preset) => (
                                <Button
                                    key={preset.label}
                                    onClick={() => handlePreset(preset)}
                                    variant={activePreset === preset.label ? 'contained' : 'outlined'}
                                    color={activePreset === preset.label ? 'primary' : 'inherit'}
                                    sx={activePreset === preset.label ? {
                                        bgcolor: 'primary.main',
                                        color: 'primary.contrastText',
                                        '&:hover': { bgcolor: 'primary.dark' },
                                    } : {}}
                                >
                                    {preset.label}
                                </Button>
                            ))}
                        </ButtonGroup>
                    </Box>

                    <Divider sx={{ opacity: 0.5 }} />

                    {/* Custom date range */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                        <Filter size={16} style={{ color: theme.palette.text.secondary, flexShrink: 0 }} />
                        <Typography variant="body2" fontWeight={600} color="text.secondary" sx={{ minWidth: 55 }}>
                            Custom:
                        </Typography>
                        <TextField
                            type="date"
                            label="From"
                            value={startDate}
                            onChange={(e) => setStartDate(e.target.value)}
                            size="small"
                            slotProps={{
                                inputLabel: { shrink: true },
                                input: { sx: { fontSize: '0.85rem', borderRadius: 2 } },
                            }}
                            sx={{ minWidth: 150 }}
                        />
                        <Typography variant="body2" color="text.disabled">to</Typography>
                        <TextField
                            type="date"
                            label="To"
                            value={endDate}
                            onChange={(e) => setEndDate(e.target.value)}
                            size="small"
                            slotProps={{
                                inputLabel: { shrink: true },
                                input: { sx: { fontSize: '0.85rem', borderRadius: 2 } },
                            }}
                            sx={{ minWidth: 150 }}
                        />
                        <Button
                            variant="contained"
                            size="small"
                            onClick={handleCustomApply}
                            sx={{ textTransform: 'none', fontWeight: 600, borderRadius: 2, px: 2.5 }}
                        >
                            Apply
                        </Button>
                        <Button
                            variant="outlined"
                            size="small"
                            color="inherit"
                            onClick={() => handlePreset(PRESETS[5])}
                            sx={{ textTransform: 'none', borderRadius: 2, px: 2, borderColor: isDark ? alpha('#fff', 0.12) : alpha('#000', 0.15) }}
                        >
                            Clear
                        </Button>
                    </Box>
                </Stack>
            </Paper>

            {error && <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{error}</Alert>}

            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                    <CircularProgress size={32} />
                </Box>
            ) : report ? (
                <>
                    {/* ─── Summary Cards ──────────────────────────── */}
                    <Grid container spacing={2} sx={{ mb: 3 }}>
                        {[
                            { label: 'Total Trades', value: stats.total_trades ?? 0, icon: <BarChart3 size={18} />, color: theme.palette.primary.main },
                            { label: 'Winners', value: stats.winners ?? 0, icon: <TrendingUp size={18} />, color: theme.palette.success.main },
                            { label: 'Losers', value: stats.losers ?? 0, icon: <TrendingDown size={18} />, color: theme.palette.error.main },
                            { label: 'Win Rate', value: `${stats.win_rate ?? 0}%`, icon: <Target size={18} />, color: (stats.win_rate ?? 0) >= 50 ? theme.palette.success.main : theme.palette.error.main },
                            { label: 'Total P&L', value: fmtINR(stats.total_pnl), icon: null, color: pctColor(stats.total_pnl, theme) },
                            { label: 'Avg Win', value: fmtINR(stats.avg_win), icon: null, color: theme.palette.success.main },
                            { label: 'Avg Loss', value: fmtINR(stats.avg_loss), icon: null, color: theme.palette.error.main },
                            { label: 'Profit Factor', value: stats.profit_factor ?? '—', icon: null, color: theme.palette.info.main },
                        ].map((item) => (
                            <Grid size={{ xs: 6, sm: 4, md: 3, lg: 1.5 }} key={item.label}>
                                <Card sx={cardSx} elevation={0}>
                                    <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 }, textAlign: 'center' }}>
                                        <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ display: 'block', mb: 0.5 }}>
                                            {item.label}
                                        </Typography>
                                        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 0.5 }}>
                                            {item.icon && <Box sx={{ color: item.color, display: 'flex' }}>{item.icon}</Box>}
                                            <Typography variant="h6" fontWeight={700} sx={{ color: item.color }}>
                                                {item.value}
                                            </Typography>
                                        </Box>
                                    </CardContent>
                                </Card>
                            </Grid>
                        ))}
                    </Grid>

                    {/* ─── Trade Table ────────────────────────────── */}
                    <Paper sx={{ ...cardSx, overflow: 'hidden' }} elevation={0}>
                        <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Clock size={16} style={{ color: theme.palette.text.secondary }} />
                            <Typography variant="subtitle1" fontWeight={600}>
                                Trade History
                            </Typography>
                            <Chip label={`${trades.length} trades`} size="small" variant="outlined" sx={{ ml: 'auto', fontSize: '0.7rem' }} />
                        </Box>
                        <TableContainer sx={{ maxHeight: 520 }}>
                            <Table size="small" stickyHeader>
                                <TableHead>
                                    <TableRow>
                                        {['Symbol', 'Type', 'Entry', 'Exit', 'Qty', 'P&L', 'P&L %', 'Entry Time', 'Exit Time'].map((h) => (
                                            <TableCell key={h} sx={{
                                                fontWeight: 700,
                                                fontSize: '0.7rem',
                                                textTransform: 'uppercase',
                                                letterSpacing: 0.5,
                                                color: 'text.secondary',
                                                bgcolor: isDark ? alpha('#fff', 0.04) : alpha('#000', 0.03),
                                            }}>
                                                {h}
                                            </TableCell>
                                        ))}
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {trades.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={9} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                                                No trades found for the selected period
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        trades.map((t, i) => (
                                            <TableRow key={i} sx={{
                                                '&:hover': { bgcolor: isDark ? alpha('#fff', 0.03) : alpha('#000', 0.02) },
                                                transition: 'background-color 0.15s',
                                            }}>
                                                <TableCell sx={{ fontWeight: 600 }}>{t.symbol}</TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={t.type}
                                                        size="small"
                                                        color={t.type === 'BUY' ? 'success' : 'error'}
                                                        sx={{ fontWeight: 700, fontSize: '0.65rem', height: 22 }}
                                                    />
                                                </TableCell>
                                                <TableCell>{t.entry_price ? fmtINR(t.entry_price) : '—'}</TableCell>
                                                <TableCell>{t.exit_price ? fmtINR(t.exit_price) : '—'}</TableCell>
                                                <TableCell>{t.quantity ?? '—'}</TableCell>
                                                <TableCell>
                                                    <Typography variant="body2" fontWeight={600}
                                                        sx={{ color: pctColor(t.pnl, theme) }}>
                                                        {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}${fmtINR(t.pnl)}` : '—'}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell>
                                                    <Typography variant="body2" fontWeight={600}
                                                        sx={{ color: pctColor(t.pnl_percent, theme) }}>
                                                        {t.pnl_percent != null ? `${t.pnl_percent >= 0 ? '+' : ''}${t.pnl_percent.toFixed(1)}%` : '—'}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell>
                                                    <Typography variant="caption" color="text.secondary">
                                                        {t.entry_time ? new Date(t.entry_time).toLocaleString('en-IN', {
                                                            day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                                                        }) : '—'}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell>
                                                    <Typography variant="caption" color="text.secondary">
                                                        {t.exit_time ? new Date(t.exit_time).toLocaleString('en-IN', {
                                                            day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                                                        }) : '—'}
                                                    </Typography>
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>
                </>
            ) : null}
        </Box>
    );
}
