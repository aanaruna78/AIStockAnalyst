import React, { useState, useEffect } from 'react';
import { Box, Typography, Stack, Link } from '@mui/material';
import { TrendingUp, TrendingDown, Newspaper } from 'lucide-react';
import axios from 'axios';
import { config } from '../config';

const TickerBar = () => {
    const [data, setData] = useState({ indices: [], news: [] });

    useEffect(() => {
        const fetchData = async () => {
            try {
                const resp = await axios.get(`${config.endpoints.scan.base}/market/status`);
                const payload = resp?.data || {};
                setData({
                    indices: Array.isArray(payload.indices) ? payload.indices : [],
                    news: Array.isArray(payload.news) ? payload.news : [],
                });
            } catch (err) {
                console.error('Ticker fetch error:', err);
                setData({ indices: [], news: [] });
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 60000); // Update every minute
        return () => clearInterval(interval);
    }, []);

    const indices = Array.isArray(data.indices) ? data.indices : [];
    const news = Array.isArray(data.news) ? data.news : [];

    if (!indices.length && !news.length) return null;

    return (
        <Box sx={{
            width: '100%',
            bgcolor: 'background.paper',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
            py: 1,
            display: 'flex',
            alignItems: 'center',
            overflow: 'hidden',
            position: 'relative',
            whiteSpace: 'nowrap',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
        }}>
            {/* Scrolling Container */}
            <Box sx={{
                display: 'inline-flex',
                animation: 'scroll 40s linear infinite',
                '&:hover': { animationPlayState: 'paused' },
                '@keyframes scroll': {
                    '0%': { transform: 'translateX(0)' },
                    '100%': { transform: 'translateX(-50%)' }
                }
            }}>
                <Stack direction="row" spacing={6} sx={{ alignItems: 'center', px: 4 }}>
                    {/* Repeat content for infinite scroll effect */}
                    {[1, 2].map((i) => (
                        <React.Fragment key={i}>
                            {/* Indices Section */}
                            {indices.map((idx, idxIndex) => (
                                <Box key={`${i}-idx-${idx.name || idxIndex}`} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Typography variant="caption" fontWeight={900} color="text.secondary">
                                        {idx.name}
                                    </Typography>
                                    <Typography variant="caption" fontWeight={700}>
                                        {idx.price.toLocaleString()}
                                    </Typography>
                                    <Typography
                                        variant="caption"
                                        fontWeight={800}
                                        sx={{
                                            color: idx.change >= 0 ? '#27c93f' : '#ff5f56',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 0.5
                                        }}
                                    >
                                        {idx.change >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                                        {idx.change_pct}%
                                    </Typography>
                                </Box>
                            ))}

                            <Box sx={{ width: 40, height: 1, bgcolor: 'rgba(255,255,255,0.1)' }} />

                            {/* News Section */}
                            {news.map((n, index) => (
                                <Box key={`${i}-news-${index}`} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Newspaper size={14} color="#00e5ff" />
                                    {n.clickable !== false ? (
                                        <Link
                                            href={n.link}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            sx={{
                                                color: 'text.primary',
                                                textDecoration: 'none',
                                                fontSize: '0.75rem',
                                                fontWeight: 500,
                                                '&:hover': { color: 'primary.main', textDecoration: 'underline' }
                                            }}
                                        >
                                            {n.title}
                                        </Link>
                                    ) : (
                                        <Typography
                                            sx={{
                                                color: 'text.primary',
                                                fontSize: '0.75rem',
                                                fontWeight: 500,
                                                cursor: 'default'
                                            }}
                                        >
                                            {n.title}
                                        </Typography>
                                    )}
                                    <Typography variant="caption" sx={{ opacity: 0.5, fontSize: '0.65rem' }}>
                                        • {n.publisher}
                                    </Typography>
                                </Box>
                            ))}
                        </React.Fragment>
                    ))}
                </Stack>
            </Box>
        </Box>
    );
};

export default TickerBar;
