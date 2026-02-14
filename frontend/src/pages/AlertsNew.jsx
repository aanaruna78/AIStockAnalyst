import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Box, Typography, Container, Card, CardContent, IconButton, Chip,
    Stack, Avatar, Tabs, Tab, Badge, alpha, useTheme, Skeleton, Button,
    Tooltip, Divider, Snackbar, Alert as MuiAlert
} from '@mui/material';
import {
    Bell, BellOff, ArrowUpRight, ArrowDownRight, TrendingUp, TrendingDown,
    AlertTriangle, CheckCircle, Clock, RefreshCw, Filter, Trash2, Eye
} from 'lucide-react';
import { fetchAlerts } from '../services/api';
import { isBullish, getDirectionColor, getDirectionBg, timeAgo, getConvictionLevel } from '../utils/formatters';
import { useNavigate } from 'react-router-dom';

const Alerts = () => {
    const _theme = useTheme();
    const navigate = useNavigate();
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState('all');
    const [dismissed, setDismissed] = useState(() => {
        try { return JSON.parse(localStorage.getItem('dismissed_alerts') || '[]'); } catch { return []; }
    });
    // Toast state
    const [toast, setToast] = useState({ open: false, message: '', severity: 'info', symbol: '' });
    const prevAlertIdsRef = useRef(new Set());

    const load = useCallback(async () => {
        try {
            setLoading(true);
            const data = await fetchAlerts();
            const newAlerts = data || [];

            // Detect new alerts and show toast
            if (prevAlertIdsRef.current.size > 0) {
                const newOnes = newAlerts.filter(a => !prevAlertIdsRef.current.has(a.id));
                if (newOnes.length > 0) {
                    const first = newOnes[0];
                    const bull = isBullish(first.direction);
                    setToast({
                        open: true,
                        message: newOnes.length === 1
                            ? `${bull ? '🟢' : '🔴'} New ${bull ? 'LONG' : 'SHORT'} signal: ${first.symbol}`
                            : `${newOnes.length} new alerts detected`,
                        severity: bull ? 'success' : 'error',
                        symbol: first.symbol
                    });
                }
            }
            prevAlertIdsRef.current = new Set(newAlerts.map(a => a.id));

            setAlerts(newAlerts);
        } catch {
            setAlerts([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); const iv = setInterval(load, 30000); return () => clearInterval(iv); }, [load]);

    const dismiss = (id) => {
        const updated = [...dismissed, id];
        setDismissed(updated);
        localStorage.setItem('dismissed_alerts', JSON.stringify(updated));
    };

    const clearDismissed = () => {
        setDismissed([]);
        localStorage.removeItem('dismissed_alerts');
    };

    const activeAlerts = alerts.filter(a => !dismissed.includes(a.id));

    const filteredAlerts = activeAlerts.filter(a => {
        if (tab === 'long') return a.direction === 'UP' || a.direction === 'Strong Up';
        if (tab === 'short') return a.direction === 'DOWN' || a.direction === 'Strong Down';
        return true;
    });

    const getSeverityIcon = (severity, direction) => {
        if (isBullish(direction)) return <ArrowUpRight size={18} />;
        return <ArrowDownRight size={18} />;
    };

    const getSeverityColor = (severity) => {
        if (severity === 'high') return '#ef4444';
        if (severity === 'medium') return '#f59e0b';
        return '#64748b';
    };

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: '-0.02em' }}>Alerts</Typography>
                        <Badge badgeContent={activeAlerts.length} color="primary" sx={{ '& .MuiBadge-badge': { fontWeight: 800 } }}>
                            <Bell size={22} />
                        </Badge>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                        Real-time alerts from AI signal engine
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    {dismissed.length > 0 && (
                        <Button size="small" variant="outlined" onClick={clearDismissed} startIcon={<RefreshCw size={14} />}
                            sx={{ borderRadius: 2, fontWeight: 600 }}>
                            Restore ({dismissed.length})
                        </Button>
                    )}
                    <IconButton onClick={load} sx={{ border: '1px solid', borderColor: 'divider' }}>
                        <RefreshCw size={18} />
                    </IconButton>
                </Box>
            </Box>

            {/* Tabs */}
            <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3, minHeight: 36, '& .MuiTab-root': { minHeight: 36, py: 0.5 } }}>
                <Tab value="all" label={`All (${activeAlerts.length})`} />
                <Tab value="long" label={`Long Signals (${activeAlerts.filter(a => isBullish(a.direction)).length})`} />
                <Tab value="short" label={`Short Signals (${activeAlerts.filter(a => !isBullish(a.direction)).length})`} />
            </Tabs>

            {/* Alert List */}
            {loading ? (
                <Stack spacing={2}>
                    {[1, 2, 3].map(i => <Skeleton key={i} variant="rectangular" height={80} sx={{ borderRadius: 4 }} />)}
                </Stack>
            ) : filteredAlerts.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 10 }}>
                    <BellOff size={56} strokeWidth={1} style={{ opacity: 0.2, marginBottom: 16 }} />
                    <Typography variant="h6" color="text.secondary" fontWeight={600}>No active alerts</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        Alerts are generated automatically when the AI engine detects new signals
                    </Typography>
                </Box>
            ) : (
                <Stack spacing={1.5}>
                    {filteredAlerts.map((alert) => {
                        const _bullish = isBullish(alert.direction);
                        const dirColor = getDirectionColor(alert.direction);
                        const _severity = getSeverityColor(alert.severity);
                        const conviction = alert.conviction || 0;
                        const _convLevel = getConvictionLevel(conviction);

                        return (
                            <Card key={alert.id} sx={{
                                position: 'relative',
                                '&:hover': { bgcolor: 'action.hover' },
                                '&::before': {
                                    content: '""', position: 'absolute', top: 0, bottom: 0, left: 0, width: 3,
                                    borderRadius: '16px 0 0 16px', bgcolor: dirColor,
                                },
                            }}>
                                <CardContent sx={{ py: 2, px: 3, '&:last-child': { pb: 2 } }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                            <Avatar sx={{ width: 40, height: 40, bgcolor: getDirectionBg(alert.direction), color: dirColor }}>
                                                {getSeverityIcon(alert.severity, alert.direction)}
                                            </Avatar>
                                            <Box>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                    <Typography variant="subtitle1" fontWeight={700}>{alert.symbol}</Typography>
                                                    <Chip label={alert.type} size="small"
                                                        sx={{ height: 20, fontSize: '0.6rem', fontWeight: 800, bgcolor: getDirectionBg(alert.direction), color: dirColor }} />
                                                    {alert.severity === 'high' && (
                                                        <Chip icon={<AlertTriangle size={10} />} label="HIGH" size="small"
                                                            sx={{ height: 20, fontSize: '0.55rem', fontWeight: 800, bgcolor: alpha('#ef4444', 0.1), color: '#ef4444', '& .MuiChip-icon': { color: '#ef4444' } }} />
                                                    )}
                                                </Box>
                                                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>{alert.message}</Typography>
                                            </Box>
                                        </Box>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                            <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
                                                <Clock size={10} style={{ marginRight: 4 }} />
                                                {timeAgo(alert.time)}
                                            </Typography>
                                            <Tooltip title="View signal">
                                                <IconButton size="small" onClick={() => navigate(`/recommendation/${alert.id}`)}>
                                                    <Eye size={16} />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="Dismiss">
                                                <IconButton size="small" onClick={() => dismiss(alert.id)} sx={{ '&:hover': { color: 'error.main' } }}>
                                                    <Trash2 size={14} />
                                                </IconButton>
                                            </Tooltip>
                                        </Box>
                                    </Box>
                                </CardContent>
                            </Card>
                        );
                    })}
                </Stack>
            )}

            {/* Toast Notification */}
            <Snackbar
                open={toast.open}
                autoHideDuration={5000}
                onClose={() => setToast(prev => ({ ...prev, open: false }))}
                anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
                <MuiAlert
                    onClose={() => setToast(prev => ({ ...prev, open: false }))}
                    severity={toast.severity}
                    variant="filled"
                    sx={{ fontWeight: 600, cursor: 'pointer', minWidth: 280 }}
                    onClick={() => {
                        setToast(prev => ({ ...prev, open: false }));
                        if (toast.symbol) {
                            const alert = alerts.find(a => a.symbol === toast.symbol);
                            if (alert) navigate(`/recommendation/${alert.id}`);
                        }
                    }}
                >
                    {toast.message}
                </MuiAlert>
            </Snackbar>
        </Container>
    );
};

export default Alerts;
