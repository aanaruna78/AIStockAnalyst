import React, { useState, useEffect, useCallback } from 'react';
import {
    Box, Typography, Container, Card, CardContent, IconButton, Chip,
    Stack, TextField, InputAdornment, Grid, Button, alpha, useTheme,
    Dialog, DialogTitle, DialogContent, DialogActions, Tooltip, Skeleton, Avatar
} from '@mui/material';
import {
    TrendingUp, TrendingDown, X, Plus, Search, Star, Eye, BarChart3,
    ArrowUpRight, ArrowDownRight, RefreshCw, Bookmark
} from 'lucide-react';
import { fetchRecommendations, fetchWatchlist, addToWatchlist, removeFromWatchlist } from '../services/api';
import { formatINR, isBullish, getDirectionColor, getDirectionBg, getDirectionLabel, timeAgo } from '../utils/formatters';

const Watchlist = () => {
    const theme = useTheme();
    const [watchlistSymbols, setWatchlistSymbols] = useState([]);
    const [recommendations, setRecommendations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [addDialogOpen, setAddDialogOpen] = useState(false);
    const [newSymbol, setNewSymbol] = useState('');

    const load = useCallback(async () => {
        try {
            setLoading(true);
            const [wl, recs] = await Promise.all([fetchWatchlist(), fetchRecommendations()]);
            setWatchlistSymbols(wl);
            setRecommendations(recs || []);
        } catch (err) {
            console.error('Failed to load watchlist:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    // Get watchlist items enriched with recommendation data
    const watchlistItems = watchlistSymbols
        .map(sym => {
            const rec = recommendations.find(r => r.symbol === sym);
            return { symbol: sym, rec };
        })
        .filter(item => !search || item.symbol.toLowerCase().includes(search.toLowerCase()));

    // Get available recommendations not yet in watchlist
    const availableToAdd = recommendations
        .filter(r => !watchlistSymbols.includes(r.symbol))
        .filter(r => !newSymbol || r.symbol.toLowerCase().includes(newSymbol.toLowerCase()));

    const handleAdd = (symbol) => {
        const updated = addToWatchlist(symbol.toUpperCase());
        setWatchlistSymbols(updated);
        setNewSymbol('');
    };

    const handleRemove = (symbol) => {
        const updated = removeFromWatchlist(symbol);
        setWatchlistSymbols(updated);
    };

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Box>
                    <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: '-0.02em' }}>Watchlist</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                        {watchlistSymbols.length} symbols tracked • Enriched with AI signals
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1.5 }}>
                    <IconButton onClick={load} sx={{ border: '1px solid', borderColor: 'divider' }}>
                        <RefreshCw size={18} />
                    </IconButton>
                    <Button variant="contained" startIcon={<Plus size={16} />} onClick={() => setAddDialogOpen(true)}
                        sx={{ borderRadius: 2, fontWeight: 700 }}>
                        Add Symbol
                    </Button>
                </Box>
            </Box>

            {/* Search */}
            <TextField fullWidth size="small" placeholder="Search watchlist..." value={search} onChange={(e) => setSearch(e.target.value)}
                slotProps={{ input: { startAdornment: <InputAdornment position="start"><Search size={16} color="#64748b" /></InputAdornment> } }}
                sx={{ mb: 3, '& .MuiOutlinedInput-root': { borderRadius: 3 } }} />

            {/* Watchlist Grid */}
            {loading ? (
                <Grid container spacing={2}>
                    {[1, 2, 3, 4].map(i => (
                        <Grid item xs={12} sm={6} md={4} key={i}>
                            <Skeleton variant="rectangular" height={160} sx={{ borderRadius: 4 }} />
                        </Grid>
                    ))}
                </Grid>
            ) : watchlistItems.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 10 }}>
                    <Bookmark size={56} strokeWidth={1} style={{ opacity: 0.2, marginBottom: 16 }} />
                    <Typography variant="h6" color="text.secondary" fontWeight={600}>
                        {watchlistSymbols.length === 0 ? 'Your watchlist is empty' : 'No matches found'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        {watchlistSymbols.length === 0 ? 'Add symbols from active signals to track them here' : 'Try a different search term'}
                    </Typography>
                    {watchlistSymbols.length === 0 && (
                        <Button variant="outlined" startIcon={<Plus size={16} />} onClick={() => setAddDialogOpen(true)} sx={{ mt: 3 }}>
                            Add your first symbol
                        </Button>
                    )}
                </Box>
            ) : (
                <Grid container spacing={2}>
                    {watchlistItems.map(({ symbol, rec }) => {
                        const hasSignal = !!rec;
                        const bullish = hasSignal ? isBullish(rec.direction) : true;
                        const dirColor = hasSignal ? getDirectionColor(rec.direction) : '#64748b';
                        const conviction = hasSignal ? (rec.conviction || rec.confidence || 0) : 0;

                        return (
                            <Grid item xs={12} sm={6} md={4} key={symbol}>
                                <Card sx={{
                                    position: 'relative',
                                    '&:hover': { transform: 'translateY(-2px)', boxShadow: `0 6px 20px ${alpha(dirColor, 0.12)}` },
                                    '&::before': hasSignal ? {
                                        content: '""', position: 'absolute', top: 0, left: 0, right: 0, height: 3,
                                        borderRadius: '16px 16px 0 0',
                                        background: `linear-gradient(90deg, ${dirColor}, ${alpha(dirColor, 0.3)})`,
                                    } : {},
                                }}>
                                    <CardContent sx={{ p: 2.5 }}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                                            <Box>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                    <Star size={14} fill={theme.palette.warning.main} color={theme.palette.warning.main} />
                                                    <Typography variant="h6" fontWeight={800}>{symbol}</Typography>
                                                </Box>
                                                {hasSignal && (
                                                    <Chip label={getDirectionLabel(rec.direction)} size="small"
                                                        icon={bullish ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
                                                        sx={{ mt: 0.5, height: 20, fontSize: '0.6rem', fontWeight: 800, bgcolor: getDirectionBg(rec.direction), color: dirColor, '& .MuiChip-icon': { color: dirColor } }} />
                                                )}
                                            </Box>
                                            <Tooltip title="Remove from watchlist">
                                                <IconButton size="small" onClick={() => handleRemove(symbol)}
                                                    sx={{ color: 'text.secondary', '&:hover': { color: 'error.main' } }}>
                                                    <X size={16} />
                                                </IconButton>
                                            </Tooltip>
                                        </Box>

                                        {hasSignal ? (
                                            <>
                                                <Typography variant="h5" fontWeight={800} sx={{ mb: 1 }}>{formatINR(rec.price || rec.entry)}</Typography>
                                                <Grid container spacing={1} sx={{ mb: 1.5 }}>
                                                    <Grid item xs={6}>
                                                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>TARGET</Typography>
                                                        <Typography variant="body2" fontWeight={700} sx={{ color: '#10b981' }}>{formatINR(rec.target1 || rec.target)}</Typography>
                                                    </Grid>
                                                    <Grid item xs={6} sx={{ textAlign: 'right' }}>
                                                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>STOP LOSS</Typography>
                                                        <Typography variant="body2" fontWeight={700} sx={{ color: '#ef4444' }}>{formatINR(rec.sl)}</Typography>
                                                    </Grid>
                                                </Grid>
                                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                    <Typography variant="caption" color="text.secondary">{conviction.toFixed(1)}% conviction</Typography>
                                                    {rec.timestamp && <Typography variant="caption" color="text.secondary">{timeAgo(rec.timestamp)}</Typography>}
                                                </Box>
                                            </>
                                        ) : (
                                            <Box sx={{ py: 2, textAlign: 'center' }}>
                                                <Typography variant="body2" color="text.secondary">No active signal</Typography>
                                                <Typography variant="caption" color="text.secondary">Waiting for next scan...</Typography>
                                            </Box>
                                        )}
                                    </CardContent>
                                </Card>
                            </Grid>
                        );
                    })}
                </Grid>
            )}

            {/* Add Symbol Dialog */}
            <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ fontWeight: 800 }}>Add to Watchlist</DialogTitle>
                <DialogContent>
                    <TextField fullWidth size="small" placeholder="Enter symbol or search active signals..." value={newSymbol}
                        onChange={(e) => setNewSymbol(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter' && newSymbol.trim()) { handleAdd(newSymbol.trim()); } }}
                        slotProps={{ input: { startAdornment: <InputAdornment position="start"><Search size={16} /></InputAdornment> } }}
                        sx={{ mt: 1, mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 2 } }} />

                    {newSymbol.trim() && !availableToAdd.find(r => r.symbol === newSymbol.toUpperCase()) && (
                        <Button variant="outlined" fullWidth onClick={() => handleAdd(newSymbol.trim())} sx={{ mb: 2 }}>
                            Add "{newSymbol.toUpperCase()}" manually
                        </Button>
                    )}

                    <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.6rem' }}>ACTIVE SIGNALS</Typography>
                    <Stack spacing={1} sx={{ mt: 1, maxHeight: 300, overflowY: 'auto' }}>
                        {availableToAdd.length === 0 ? (
                            <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                                {newSymbol ? 'No matching signals' : 'All signals already in watchlist'}
                            </Typography>
                        ) : availableToAdd.map(r => (
                            <Box key={r.symbol} sx={{
                                p: 1.5, borderRadius: 2, border: '1px solid', borderColor: 'divider',
                                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                '&:hover': { bgcolor: 'action.hover' }, cursor: 'pointer'
                            }} onClick={() => handleAdd(r.symbol)}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                    <Chip label={getDirectionLabel(r.direction)} size="small"
                                        sx={{ height: 20, fontSize: '0.6rem', fontWeight: 800, bgcolor: getDirectionBg(r.direction), color: getDirectionColor(r.direction) }} />
                                    <Typography variant="body2" fontWeight={700}>{r.symbol}</Typography>
                                    <Typography variant="caption" color="text.secondary">{formatINR(r.price || r.entry)}</Typography>
                                </Box>
                                <Plus size={16} />
                            </Box>
                        ))}
                    </Stack>
                </DialogContent>
                <DialogActions sx={{ p: 2 }}>
                    <Button onClick={() => setAddDialogOpen(false)}>Close</Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
};

export default Watchlist;
