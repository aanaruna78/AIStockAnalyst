import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Container, Grid, Card, CardContent,
    Chip, Button, Stack, LinearProgress, Skeleton, alpha, useTheme, Divider, Avatar
} from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import {
    ArrowLeft, TrendingUp, TrendingDown, ShieldCheck, Clock, Target,
    BarChart3, Zap, Activity, BookmarkPlus, AlertTriangle
} from 'lucide-react';
import RationaleRenderer from '../components/RationaleRenderer';
import { fetchRecommendationById } from '../services/api';
import { addToWatchlist } from '../services/api';
import { formatINR, isBullish, getDirectionColor, getDirectionBg, getDirectionLabel, getConvictionLevel, SCORE_COLORS, timeAgo } from '../utils/formatters';

const RecommendationDetail = () => {
    const navigate = useNavigate();
    const { id } = useParams();
    const theme = useTheme();
    const [rec, setRec] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const data = await fetchRecommendationById(id);
                setRec(data);
            } catch (err) {
                console.error('Failed to load recommendation:', err);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [id]);

    if (loading) {
        return (
            <Container maxWidth="lg" sx={{ py: 4 }}>
                <Skeleton variant="text" width={200} height={40} sx={{ mb: 2 }} />
                <Grid container spacing={3}>
                    <Grid size={{ xs: 12, md: 8 }}><Skeleton variant="rectangular" height={400} sx={{ borderRadius: 4 }} /></Grid>
                    <Grid size={{ xs: 12, md: 4 }}><Skeleton variant="rectangular" height={400} sx={{ borderRadius: 4 }} /></Grid>
                </Grid>
            </Container>
        );
    }

    if (!rec) {
        return (
            <Container maxWidth="lg" sx={{ py: 4, textAlign: 'center' }}>
                <AlertTriangle size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
                <Typography variant="h6" color="text.secondary">Recommendation not found</Typography>
                <Button startIcon={<ArrowLeft size={16} />} onClick={() => navigate('/')} sx={{ mt: 2 }}>
                    Back to Dashboard
                </Button>
            </Container>
        );
    }

    const bullish = isBullish(rec.direction);
    const dirColor = getDirectionColor(rec.direction);
    const conviction = rec.conviction || rec.confidence || 0;
    const convLevel = getConvictionLevel(conviction);
    const price = rec.price || rec.entry;

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Button startIcon={<ArrowLeft size={16} />} onClick={() => navigate('/')} sx={{ mb: 3, color: 'text.secondary', fontWeight: 600 }}>
                Back to Dashboard
            </Button>

            <Grid container spacing={3}>
                {/* Left Column - Analysis */}
                <Grid size={{ xs: 12, md: 8 }}>
                    {/* Header Card */}
                    <Card sx={{ mb: 3, position: 'relative', overflow: 'visible',
                        '&::before': { content: '""', position: 'absolute', top: 0, left: 0, right: 0, height: 4, borderRadius: '16px 16px 0 0', background: `linear-gradient(90deg, ${dirColor}, ${alpha(dirColor, 0.3)})` }
                    }}>
                        <CardContent sx={{ p: 3 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <Avatar sx={{ width: 56, height: 56, bgcolor: getDirectionBg(rec.direction), color: dirColor }}>
                                        {bullish ? <TrendingUp size={28} /> : <TrendingDown size={28} />}
                                    </Avatar>
                                    <Box>
                                        <Typography variant="h3" fontWeight={800} sx={{ letterSpacing: '-0.02em' }}>{rec.symbol}</Typography>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                                            <Chip label={getDirectionLabel(rec.direction)} size="small"
                                                sx={{ fontWeight: 800, bgcolor: getDirectionBg(rec.direction), color: dirColor, border: `1px solid ${alpha(dirColor, 0.2)}` }} />
                                            {rec.timestamp && (
                                                <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                    <Clock size={11} /> {timeAgo(rec.timestamp)}
                                                </Typography>
                                            )}
                                        </Box>
                                    </Box>
                                </Box>
                                <Box sx={{ textAlign: 'right' }}>
                                    <Typography variant="overline" color="text.secondary">ENTRY PRICE</Typography>
                                    <Typography variant="h4" fontWeight={800}>{formatINR(price)}</Typography>
                                </Box>
                            </Box>

                            {/* Trade Levels */}
                            <Grid container spacing={2}>
                                <Grid size={4}>
                                    <Box sx={{ p: 2, borderRadius: 3, bgcolor: alpha('#10b981', 0.06), border: `1px solid ${alpha('#10b981', 0.1)}`, textAlign: 'center' }}>
                                        <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.55rem' }}>
                                            <Target size={10} style={{ marginRight: 4 }} />TARGET 1
                                        </Typography>
                                        <Typography variant="h6" fontWeight={800} sx={{ color: '#10b981' }}>{formatINR(rec.target1 || rec.target)}</Typography>
                                    </Box>
                                </Grid>
                                <Grid size={4}>
                                    <Box sx={{ p: 2, borderRadius: 3, bgcolor: alpha('#6366f1', 0.06), border: `1px solid ${alpha('#6366f1', 0.1)}`, textAlign: 'center' }}>
                                        <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.55rem' }}>
                                            <Target size={10} style={{ marginRight: 4 }} />TARGET 2
                                        </Typography>
                                        <Typography variant="h6" fontWeight={800} sx={{ color: '#6366f1' }}>{rec.target2 ? formatINR(rec.target2) : '---'}</Typography>
                                    </Box>
                                </Grid>
                                <Grid size={4}>
                                    <Box sx={{ p: 2, borderRadius: 3, bgcolor: alpha('#ef4444', 0.06), border: `1px solid ${alpha('#ef4444', 0.1)}`, textAlign: 'center' }}>
                                        <Typography variant="overline" color="text.secondary" sx={{ fontSize: '0.55rem' }}>
                                            <ShieldCheck size={10} style={{ marginRight: 4 }} />STOP LOSS
                                        </Typography>
                                        <Typography variant="h6" fontWeight={800} sx={{ color: '#ef4444' }}>{formatINR(rec.sl)}</Typography>
                                    </Box>
                                </Grid>
                            </Grid>
                        </CardContent>
                    </Card>

                    {/* AI Analysis */}
                    <Card sx={{ mb: 3 }}>
                        <CardContent sx={{ p: 3 }}>
                            <Typography variant="subtitle2" fontWeight={800} color="primary.main" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                <Zap size={16} /> AI ANALYSIS & RATIONALE
                            </Typography>
                            <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: alpha(theme.palette.primary.main, 0.04), border: `1px solid ${alpha(theme.palette.primary.main, 0.08)}` }}>
                                <RationaleRenderer content={rec.rationale || 'No detailed rationale available.'} />
                            </Box>
                        </CardContent>
                    </Card>

                    {/* Score Breakdown */}
                    {rec.score_breakdown && (
                        <Card>
                            <CardContent sx={{ p: 3 }}>
                                <Typography variant="subtitle2" fontWeight={800} color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, fontSize: '0.8rem' }}>
                                    <BarChart3 size={16} /> SCORE BREAKDOWN (WEIGHTED)
                                </Typography>
                                <Grid container spacing={2}>
                                    {Object.entries(rec.score_breakdown).map(([label, rawVal]) => {
                                        const val = Math.max(0, Math.min(100, Math.abs(rawVal)));
                                        const color = SCORE_COLORS[label] || '#94a3b8';
                                        return (
                                            <Grid size={{ xs: 12, sm: 6 }} key={label}>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                                    <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: color, flexShrink: 0 }} />
                                                    <Box sx={{ flex: 1 }}>
                                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                                            <Typography variant="body2" fontWeight={600}>{label}</Typography>
                                                            <Typography variant="body2" fontWeight={800} sx={{ color: val >= 50 ? '#10b981' : val >= 20 ? '#f59e0b' : 'text.secondary' }}>
                                                                {Math.round(val)}%
                                                            </Typography>
                                                        </Box>
                                                        <LinearProgress variant="determinate" value={Math.min(val, 100)}
                                                            sx={{ height: 4, borderRadius: 2, bgcolor: alpha(color, 0.1), '& .MuiLinearProgress-bar': { bgcolor: color } }} />
                                                    </Box>
                                                </Box>
                                            </Grid>
                                        );
                                    })}
                                </Grid>
                            </CardContent>
                        </Card>
                    )}
                </Grid>

                {/* Right Column - Actions & Info */}
                <Grid size={{ xs: 12, md: 4 }}>
                    {/* Conviction Card */}
                    <Card sx={{ mb: 3 }}>
                        <CardContent sx={{ p: 3, textAlign: 'center' }}>
                            <Typography variant="overline" color="text.secondary">CONVICTION SCORE</Typography>
                            <Box sx={{ position: 'relative', display: 'inline-flex', my: 2 }}>
                                <Box sx={{
                                    width: 100, height: 100, borderRadius: '50%',
                                    border: `4px solid ${alpha(convLevel.color, 0.2)}`,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    background: `conic-gradient(${convLevel.color} ${conviction * 3.6}deg, ${alpha(convLevel.color, 0.08)} 0deg)`,
                                }}>
                                    <Box sx={{ width: 80, height: 80, borderRadius: '50%', bgcolor: 'background.paper', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
                                        <Typography variant="h5" fontWeight={800} sx={{ color: convLevel.color }}>{conviction.toFixed(1)}%</Typography>
                                    </Box>
                                </Box>
                            </Box>
                            <Chip label={convLevel.label} size="small" sx={{ fontWeight: 800, color: convLevel.color, bgcolor: alpha(convLevel.color, 0.1), border: `1px solid ${alpha(convLevel.color, 0.2)}` }} />
                        </CardContent>
                    </Card>

                    {/* Actions */}
                    <Card sx={{ mb: 3 }}>
                        <CardContent sx={{ p: 3 }}>
                            <Typography variant="subtitle2" fontWeight={800} color="text.secondary" sx={{ mb: 2, fontSize: '0.75rem' }}>ACTIONS</Typography>
                            <Stack spacing={1.5}>
                                <Button variant="outlined" fullWidth startIcon={<BookmarkPlus size={16} />}
                                    onClick={() => addToWatchlist(rec.symbol)} sx={{ justifyContent: 'flex-start', fontWeight: 600 }}>
                                    Add to Watchlist
                                </Button>
                                <Button variant="outlined" fullWidth startIcon={<Activity size={16} />}
                                    onClick={() => navigate('/portfolio')} sx={{ justifyContent: 'flex-start', fontWeight: 600 }}>
                                    View Portfolio
                                </Button>
                            </Stack>
                        </CardContent>
                    </Card>

                    {/* Trade Management */}
                    <Card>
                        <CardContent sx={{ p: 3 }}>
                            <Typography variant="subtitle2" fontWeight={800} color="text.secondary" sx={{ mb: 2, fontSize: '0.75rem' }}>
                                TRADE MANAGEMENT
                            </Typography>
                            <Box sx={{ p: 2, borderRadius: 3, bgcolor: alpha('#f59e0b', 0.04), border: `1px solid ${alpha('#f59e0b', 0.1)}`, mb: 2 }}>
                                <Typography variant="overline" sx={{ fontSize: '0.55rem', color: '#f59e0b' }}>TRAILING SL STRATEGY</Typography>
                                <Typography variant="body2" fontWeight={600} sx={{ mt: 0.5 }}>
                                    Move SL to entry ({formatINR(price)}) after T1 ({formatINR(rec.target1 || rec.target)}) is hit.
                                </Typography>
                            </Box>
                            <Divider sx={{ my: 2 }} />
                            <Typography variant="caption" color="text.secondary">
                                Risk/Reward signals generated by AI. Always verify with your own analysis. Past performance is not indicative of future results.
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </Container>
    );
};

export default RecommendationDetail;
