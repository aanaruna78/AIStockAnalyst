import React, { useState, useEffect } from 'react';
import {
    Box, Button, TextField, Typography, Card, CardContent, Container,
    Divider, Stack, Alert, CircularProgress, IconButton, InputAdornment,
} from '@mui/material';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import { useAuth } from '../context/AuthContext';
import { config } from '../config';
import { loginWithEmail } from '../services/api';
import axios from 'axios';

const Login = () => {
    const { user, login, loading: authLoading } = useAuth();
    const navigate = useNavigate();

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        if (!authLoading && user) {
            navigate(user.onboarded ? '/' : '/onboarding', { replace: true });
        }
    }, [user, authLoading, navigate]);

    // ─── Email/password login ────────────────────────────────────
    const handleEmailLogin = async (e) => {
        e.preventDefault();
        setError('');
        if (!email || !password) { setError('Please fill in all fields'); return; }

        setSubmitting(true);
        try {
            const data = await loginWithEmail(email, password);
            if (data.access_token) {
                login(data.access_token, data.user);
                navigate('/', { replace: true });
            }
        } catch (err) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Login failed. Check your credentials.');
        } finally {
            setSubmitting(false);
        }
    };

    // ─── Google SSO login ────────────────────────────────────────
    const handleGoogleSuccess = async (credentialResponse) => {
        setError('');
        try {
            const response = await axios.post(`${config.API_BASE_URL}/auth/google`, {
                token: credentialResponse.credential,
            });
            const { access_token, user: userData } = response.data;
            if (access_token) {
                login(access_token, userData);
                if (userData?.preferences) {
                    localStorage.setItem('user_preferences', JSON.stringify({
                        risk: userData.preferences.risk_tolerance || 'medium',
                        horizon: userData.preferences.investment_horizon || 'swing',
                        sectors: userData.preferences.preferred_sectors || [],
                    }));
                }
                navigate('/', { replace: true });
            }
        } catch (err) {
            console.error('Google Login Error:', err);
            setError('Google authentication failed. Please try again.');
        }
    };

    if (authLoading) return null;

    return (
        <Container maxWidth="sm" sx={{ py: 8 }}>
            <Card sx={{ borderRadius: 4, overflow: 'hidden' }}>
                {/* Header */}
                <Box sx={{
                    p: 4, textAlign: 'center',
                    background: 'linear-gradient(135deg, rgba(56,189,248,0.08) 0%, rgba(129,140,248,0.08) 100%)',
                }}>
                    <Typography variant="h3" fontWeight={900} sx={{ letterSpacing: '-0.03em', mb: 1 }}>
                        SignalForge
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        AI-Powered Stock Trading Signals
                    </Typography>
                </Box>

                <CardContent sx={{ p: 4 }}>
                    <Typography variant="h6" align="center" sx={{ mb: 3 }}>
                        Sign in to your account
                    </Typography>

                    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                    {/* Email / Password form */}
                    <Box component="form" onSubmit={handleEmailLogin} noValidate>
                        <TextField
                            fullWidth label="Email" type="email" value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            margin="normal" autoComplete="email" autoFocus
                        />
                        <TextField
                            fullWidth label="Password" value={password}
                            type={showPassword ? 'text' : 'password'}
                            onChange={(e) => setPassword(e.target.value)}
                            margin="normal" autoComplete="current-password"
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <IconButton onClick={() => setShowPassword(!showPassword)} edge="end">
                                            {showPassword ? <VisibilityOff /> : <Visibility />}
                                        </IconButton>
                                    </InputAdornment>
                                ),
                            }}
                        />
                        <Button
                            type="submit" fullWidth variant="contained" size="large"
                            disabled={submitting}
                            sx={{ mt: 2, py: 1.5, fontWeight: 700, boxShadow: '0 0 15px rgba(0, 242, 254, 0.4)' }}
                        >
                            {submitting ? <CircularProgress size={22} /> : 'Sign In'}
                        </Button>
                    </Box>

                    <Divider sx={{ my: 3 }}>
                        <Typography variant="caption" color="text.secondary">OR</Typography>
                    </Divider>

                    {/* Google SSO */}
                    <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
                        <GoogleLogin
                            onSuccess={handleGoogleSuccess}
                            onError={() => setError('Google login failed')}
                            useOneTap
                            theme="filled_blue"
                            shape="pill"
                            size="large"
                            width={300}
                        />
                    </Box>

                    <Divider sx={{ mb: 2 }} />

                    <Typography variant="body2" align="center" color="text.secondary">
                        Don't have an account?{' '}
                        <Typography
                            component={RouterLink} to="/register"
                            variant="body2" color="primary" fontWeight={600}
                            sx={{ textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
                        >
                            Register here
                        </Typography>
                    </Typography>
                </CardContent>
            </Card>
        </Container>
    );
};

export default Login;
