import React, { useState, useEffect } from 'react';
import { AppBar, Toolbar, Typography, Box, Button, IconButton, Avatar, Menu, MenuItem, Tooltip } from '@mui/material';
import { Sun, Moon, LogOut, User as UserIcon, Settings } from 'lucide-react';
import { useColorMode } from '../context/ThemeContext';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { config } from '../config';

const Header = () => {
    const { toggleColorMode } = useColorMode();
    const [user, setUser] = useState(null);
    const [anchorEl, setAnchorEl] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        const fetchUser = async () => {
            const token = localStorage.getItem('token');
            if (token) {
                try {
                    const response = await axios.get(config.endpoints.auth.me, {
                        headers: { Authorization: `Bearer ${token}` }
                    });
                    setUser(response.data);
                } catch (error) {
                    console.error('Failed to fetch user:', error);
                    // If unauthorized, clear token
                    if (error.response?.status === 401 || error.response?.status === 404) {
                        localStorage.removeItem('token');
                        setUser(null);
                    }
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

    return (
        <AppBar position="sticky" elevation={0}>
            <Toolbar sx={{ justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, textDecoration: 'none' }} component={Link} to="/">
                    <img src="/logo.png" alt="SignalForge Icon" style={{ height: 40 }} />
                    <Box>
                        <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1, fontSize: '1.2rem', color: 'primary.main', letterSpacing: -0.5 }}>
                            SignalForge
                        </Typography>
                        <Typography variant="caption" sx={{ fontSize: '0.7rem', fontWeight: 600, color: 'text.secondary', display: 'block', mt: 0.2 }}>
                            Your AI Powered trading companion
                        </Typography>
                    </Box>
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Button
                        component={Link}
                        to="/portfolio"
                        color="inherit"
                        sx={{ fontWeight: 700, color: 'text.secondary', '&:hover': { color: 'primary.main' } }}
                    >
                        Trading
                    </Button>
                    <IconButton onClick={toggleColorMode} color="inherit">
                        {localStorage.getItem('theme_mode') === 'light' ? <Moon size={20} /> : <Sun size={20} />}
                    </IconButton>

                    {user ? (
                        <>
                            <Tooltip title="Account settings">
                                <IconButton onClick={handleMenuOpen} size="small" sx={{ ml: 1 }}>
                                    <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main', color: 'primary.contrastText', fontSize: '0.9rem', fontWeight: 700 }}>
                                        {user.full_name ? user.full_name[0].toUpperCase() : 'U'}
                                    </Avatar>
                                </IconButton>
                            </Tooltip>
                            <Menu
                                anchorEl={anchorEl}
                                open={Boolean(anchorEl)}
                                onClose={handleMenuClose}
                                transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                                anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
                                PaperProps={{
                                    sx: { mt: 1.5, minWidth: 180, bgcolor: 'background.paper', border: '1px solid rgba(255,255,255,0.1)' }
                                }}
                            >
                                <Box sx={{ px: 2, py: 1.5 }}>
                                    <Typography variant="subtitle2" fontWeight={700}>{user.full_name}</Typography>
                                    <Typography variant="caption" color="text.secondary">{user.email}</Typography>
                                </Box>
                                <MenuItem onClick={() => { handleMenuClose(); navigate('/portfolio'); }}>
                                    <UserIcon size={16} style={{ marginRight: 12 }} /> Profile
                                </MenuItem>
                                <MenuItem onClick={handleLogout}>
                                    <LogOut size={16} style={{ marginRight: 12 }} /> Logout
                                </MenuItem>
                            </Menu>
                        </>
                    ) : (
                        <Button component={Link} to="/onboarding" variant="contained" size="small">
                            Sign In
                        </Button>
                    )}
                </Box>
            </Toolbar>
        </AppBar>
    );
};

export default Header;
