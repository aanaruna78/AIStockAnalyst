import React from 'react';
import {
    Box, Typography, Container, List, ListItem,
    ListItemText, ListItemAvatar, Avatar, IconButton,
    Chip, Stack, Divider, Paper
} from '@mui/material';
import { TrendingUp, TrendingDown, X, Plus } from 'lucide-react';

const Watchlist = () => {
    const stocks = [
        { symbol: 'INFY', price: '1620.40', change: '+1.2%', up: true },
        { symbol: 'BHARTIARTL', price: '1240.15', change: '-0.4%', up: false },
        { symbol: 'WIPRO', price: '540.20', change: '+2.5%', up: true },
    ];

    return (
        <Container maxWidth="md" sx={{ py: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Typography variant="h4" fontWeight={700}>My Watchlist</Typography>
                <IconButton color="primary" sx={{ border: '1px solid', borderColor: 'primary.main' }}>
                    <Plus size={20} />
                </IconButton>
            </Box>

            <Paper variant="outlined" sx={{ bgcolor: 'rgba(255,255,255,0.02)' }}>
                <List sx={{ p: 0 }}>
                    {stocks.map((stock, index) => (
                        <React.Fragment key={stock.symbol}>
                            <ListItem
                                sx={{
                                    py: 2,
                                    px: 3,
                                    '&:hover': { bgcolor: 'rgba(255,255,255,0.05)', cursor: 'pointer' }
                                }}
                                secondaryAction={
                                    <Stack direction="row" spacing={2} alignItems="center">
                                        <Box sx={{ textAlign: 'right' }}>
                                            <Typography variant="body1" fontWeight={600}>₹{stock.price}</Typography>
                                            <Typography variant="caption" color={stock.up ? 'success.main' : 'error.main'}>
                                                {stock.change}
                                            </Typography>
                                        </Box>
                                        <IconButton size="small" color="inherit">
                                            <X size={18} />
                                        </IconButton>
                                    </Stack>
                                }
                            >
                                <ListItemAvatar>
                                    <Avatar sx={{ bgcolor: stock.up ? 'rgba(0,230,118,0.1)' : 'rgba(255,23,68,0.1)', color: stock.up ? 'success.main' : 'error.main' }}>
                                        {stock.up ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
                                    </Avatar>
                                </ListItemAvatar>
                                <ListItemText
                                    primary={<Typography variant="h6" fontWeight={700}>{stock.symbol}</Typography>}
                                    secondary="NSE Market"
                                />
                            </ListItem>
                            {index < stocks.length - 1 && <Divider />}
                        </React.Fragment>
                    ))}
                </List>
            </Paper>
        </Container>
    );
};

export default Watchlist;
