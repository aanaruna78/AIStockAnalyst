import React, { useState, useEffect } from 'react';
import { AppBar, Toolbar, Typography, Box, Button, IconButton, Avatar, Menu, MenuItem, Tooltip, Badge, Chip, alpha, Divider } from '@mui/material';
import { Sun, Moon, LogOut, User as UserIcon, Settings, Bell, Activity, TrendingUp, BarChart3, Bookmark, Bot, Zap } from 'lucide-react';
import { useColorMode } from '../context/ThemeContext';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import { config } from '../config';

const navItems = [
    { label: 'Signals', path: '/', icon: <Zap size={16} /> },
    { label: 'Portfolio', path: '/portfolio', icon: <BarChart3 size={16} /> },
    { label: 'Watchlist', path: '/watchlist', icon: <Bookmark size={16} /> },
    { label: 'Alerts', path: '/alerts', icon: <Bell size={16} /> },
    { label: 'Agent', path: '/agent', icon: <Bot size={16} /> },
];

const Header = () => {
    const { toggleColorMode } = useColorMode();
    const [user, setUser] = useState(null);
    const [anchorEl, setAnchorEl] = useState(null);
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        const fetchUser = async () => {
            const token = localStorage.getItem('token');
            if (!token) return;
            try {
                const response = await axios.get(config.endpoints.auth.me, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                setUser(response.data);
            } catch (error) {
                if (error.response?.status === 401 || error.response?.status === 404) {
                    localStorage.removeItem('token');
                    setUser(null);
                }
            }
        };
        fetchUser();
    }, []);

    const handleMenuOpen = (event) => setAnchorEl(event.currentTarget);
    const handleMenuClose = () => setAnchorEl(null);

    const handleLogout = () => {
        localStorage.removeItem('token');
        setUser(null);
        handleMenuClose();
        navigate('/onboarding');
    };

    const isDark = localStorage.getItem('theme_mode') !== 'light';

    return (
        <AppBar position="sticky" elevation={0}>
            <Toolbar sx={{ justifyContent: 'space-between', px: { xs: 2, md: 4 }, minHeight: '64px !important' }}>
                {/* Logo */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, textDecoration: 'none' }} component={Link} to="/">
                    <Box sx={{
                        width: 36, height: 36, borderRadius: 2,
                        background: 'linear-gradient(135deg, #38bdf8, #818cf8)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <TrendingUp size={20} color="#fff" />
                    </Box>
                    <Box>
                        <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1, fontSize: '1.1rem', color: 'primary.main', letterSpacing: '-0.02em' }}>
                            SignalForge
                        </Typography>
                        <Typography variant="caption" sx={{ fontSize: '0.6rem', fontWeight: 500, color: 'text.secondary', display: 'block', mt: 0.1 }}>
                            AI-Powered Trading Platform
                        </Typography>
                    </Box>
                </Box>

                {/* Navigation */}
                <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 0.5 }}>
                    {navItems.map(({ label, path, icon }) => {
                        const active = location.pathname === path;
                        return (
                            <Button key={path} component={Link} to={path} size="small"
                                startIcon={icon}
                                sx={{
                                    fontWeight: active ? 700 : 500,
                                    fontSize: '0.8rem',
                                    color: active ? 'primary.main' : 'text.secondary',
                                    bgcolor: active ? (t) => alpha(t.palette.primary.main, 0.08) : 'transparent',
                                    borderRadius: 2,
                                    px: 1.5,
                                    py: 0.75,
                                    minWidth: 'unset',
                                    '&:hover': {
                                        bgcolor: (t) => alpha(t.palette.primary.main, 0.06),
                                        color: 'primary.main',
                                    },
                                }}>
                                {label}
                            </Button>
                        );
                    })}
                </Box>

                {/* Right Actions */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Tooltip title={isDark ? 'Light mode' : 'Dark mode'}>
                        <IconButton onClick={toggleColorMode} size="small" sx={{ color: 'text.secondary' }}>
                            {isDark ? <Sun size={18} /> : <Moon size={18} />}
                        </IconButton>
                    </Tooltip>

                    {user ? (
                        <>
                            <Tooltip title="Account">
                                <IconButton onClick={handleMenuOpen} size="small" sx={{ ml: 0.5 }}>
                                    <Avatar sx={{
                                        width: 32, height: 32, fontSize: '0.85rem', fontWeight: 700,
                                        background: 'linear-gradient(135deg, #38bdf8, #818cf8)',
                                        color: '#fff',
                                    }}>
                                        {user.full_name ? user.full_name[0].toUpperCase() : 'U'}
                                    </Avatar>
                                </IconButton>
                            </Tooltip>
                            <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleMenuClose}
                                transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                                anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
                                slotProps={{ paper: { sx: { mt: 1.5, minWidth: 200, borderRadius: 3, border: '1px solid', borderColor: 'divider' } } }}>
                                <Box sx={{ px: 2, py: 1.5 }}>
                                    <Typography variant="subtitle2" fontWeight={700}>{user.full_name}</Typography>
                                    <Typography variant="caption" color="text.secondary">{user.email}</Typography>
                                </Box>
                                <Divider />
                                <MenuItem onClick={() => { handleMenuClose(); navigate('/portfolio'); }}>
                                    <UserIcon size={16} style={{ marginRight: 12 }} /> Profile
                                </MenuItem>
                                <MenuItem onClick={handleLogout}>
                                    <LogOut size={16} style={{ marginRight: 12 }} /> Logout
                                </MenuItem>
                            </Menu>
                        </>
                    ) : (
                        <Button component={Link} to="/onboarding" variant="contained" size="small" sx={{ borderRadius: 2, fontWeight: 700, px: 2 }}>
                            Sign In
                        </Button>
                    )}
                </Box>
            </Toolbar>
        </AppBar>
    );
};

export default Header;
