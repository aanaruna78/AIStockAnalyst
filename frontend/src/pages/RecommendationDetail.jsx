import React from 'react';
import {
    Box, Typography, Container, Grid, Card, CardContent,
    Chip, Button, Divider, Stack, LinearProgress
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import {
    ArrowLeft, Info, TrendingUp, ShieldCheck,
    Clock, Share2, BookmarkPlus, Zap
} from 'lucide-react';
import RationaleRenderer from '../components/RationaleRenderer';

const RecommendationDetail = () => {
    const navigate = useNavigate();

    // Mock data for the specific ID
    const rec = {
        symbol: 'RELIANCE',
        direction: 'Strong Up',
        price: '2984.50',
        target1: '3020.00',
        target2: '3050.00',
        sl: '2940.00',
        confidence: 92,
        validity: '22 Jan, 15:30',
        rationale: 'Prices have broken out of a 6-month consolidation range on high volume. Convergence of 50-day and 200-day EMA suggests a strong bullish trend initiation. Stochastic RSI is in the neutral zone, providing room for upside movement.',
        metrics: [
            { label: 'Sentiment', value: 85 },
            { label: 'Volume Flow', value: 78 },
            { label: 'Trend Strength', value: 90 }
        ]
    };

    return (
        <Container maxWidth="md" sx={{ py: 4 }}>
            <Button
                startIcon={<ArrowLeft size={18} />}
                onClick={() => navigate('/')}
                sx={{ mb: 3, color: 'text.secondary' }}
            >
                Back to Dashboard
            </Button>

            <Grid container spacing={4}>
                <Grid size={{ xs: 12, md: 8 }}>
                    <Box sx={{ mb: 4 }}>
                        <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 1 }}>
                            <Typography variant="h3" fontWeight={700}>{rec.symbol}</Typography>
                            <Chip label={rec.direction} color="success" sx={{ fontWeight: 700 }} />
                        </Stack>
                        <Typography variant="h4" color="text.primary">₹{rec.price}</Typography>
                    </Box>

                    <Card variant="outlined" sx={{ mb: 4, bgcolor: 'rgba(255,255,255,0.02)' }}>
                        <CardContent>
                            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Zap size={20} color="#00f2fe" /> AI Rationale
                            </Typography>
                            <Typography component="div" variant="body1" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                                <RationaleRenderer content={rec.rationale} />
                            </Typography>
                        </CardContent>
                    </Card>

                    <Typography variant="h6" gutterBottom>Technical Metrics</Typography>
                    <Stack spacing={2} sx={{ mb: 4 }}>
                        {rec.metrics.map((m) => (
                            <Box key={m.label}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                    <Typography variant="body2">{m.label}</Typography>
                                    <Typography variant="body2" color="primary">{m.value}%</Typography>
                                </Box>
                                <LinearProgress variant="determinate" value={m.value} sx={{ height: 6, borderRadius: 3 }} />
                            </Box>
                        ))}
                    </Stack>
                </Grid>

                <Grid size={{ xs: 12, md: 4 }}>
                    <Stack spacing={3}>
                        <Card>
                            <CardContent>
                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>EXECUTION LEVELS</Typography>
                                <Divider sx={{ mb: 2 }} />

                                <Stack spacing={2.5}>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Target 1</Typography>
                                        <Typography variant="h6" color="success.main">₹{rec.target1}</Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Target 2</Typography>
                                        <Typography variant="h6" color="success.main">₹{rec.target2}</Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Stop Loss</Typography>
                                        <Typography variant="h6" color="error.main">₹{rec.sl}</Typography>
                                    </Box>
                                </Stack>
                            </CardContent>
                        </Card>

                        <Button variant="contained" fullWidth size="large" sx={{ py: 1.5 }}>
                            Execute with Dhan
                        </Button>

                        <Stack direction="row" spacing={2}>
                            <Button fullWidth variant="outlined" startIcon={<BookmarkPlus size={18} />}>
                                Save
                            </Button>
                            <Button fullWidth variant="outlined" startIcon={<Share2 size={18} />}>
                                Share
                            </Button>
                        </Stack>

                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary' }}>
                            <Clock size={16} />
                            <Typography variant="caption">Valid until {rec.validity}</Typography>
                        </Box>
                    </Stack>
                </Grid>
            </Grid>
        </Container>
    );
};

export default RecommendationDetail;
