import React from 'react';
import {
    Box, Typography, Container, Card, CardContent,
    Stack, Avatar, IconButton, Chip, Divider, List, ListItem
} from '@mui/material';
import { Bell, BellOff, ArrowUpRight, ArrowDownRight, MoreVertical } from 'lucide-react';

const Alerts = () => {
    const alerts = [
        { id: 1, type: 'Target Hit', symbol: 'TCS', message: 'Target 1 of ₹4020.00 reached.', time: '10 mins ago', color: 'success' },
        { id: 2, type: 'Price Alert', symbol: 'HDFCBANK', message: 'Price dropped below ₹1640.00.', time: '1 hour ago', color: 'error' },
        { id: 3, type: 'Entry Alert', symbol: 'RELIANCE', message: 'Entered the buy range ₹2980-₹2990.', time: '2 hours ago', color: 'primary' },
    ];

    return (
        <Container maxWidth="md" sx={{ py: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Typography variant="h4" fontWeight={700}>System Alerts</Typography>
                <IconButton color="primary">
                    <Bell size={24} />
                </IconButton>
            </Box>

            <Stack spacing={2}>
                {alerts.map((alert) => (
                    <Card key={alert.id} sx={{ bgcolor: 'rgba(255,255,255,0.02)' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <Stack direction="row" spacing={2} alignItems="center">
                                    <Avatar sx={{ bgcolor: `${alert.color}.main`, width: 40, height: 40 }}>
                                        {alert.type.includes('Target') || alert.type.includes('Entry') ? <ArrowUpRight size={20} /> : <ArrowDownRight size={20} />}
                                    </Avatar>
                                    <Box>
                                        <Typography variant="subtitle1" fontWeight={700}>{alert.symbol} - {alert.type}</Typography>
                                        <Typography variant="body2" color="text.secondary">{alert.message}</Typography>
                                    </Box>
                                </Stack>
                                <Box sx={{ textAlign: 'right' }}>
                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                                        {alert.time}
                                    </Typography>
                                    <IconButton size="small"><MoreVertical size={16} /></IconButton>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                ))}

                {alerts.length === 0 && (
                    <Box sx={{ textAlign: 'center', py: 8 }}>
                        <BellOff size={48} color="rgba(255,255,255,0.2)" />
                        <Typography variant="h6" color="text.secondary" sx={{ mt: 2 }}>No new alerts</Typography>
                    </Box>
                )}
            </Stack>
        </Container>
    );
};

export default Alerts;
