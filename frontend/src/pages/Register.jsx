import React, { useState, useEffect, useRef } from 'react';
import {
    Box, Button, TextField, Typography, Card, CardContent, Container,
    Alert, CircularProgress, IconButton, InputAdornment, LinearProgress,
    List, ListItem, ListItemIcon, ListItemText, Chip,
} from '@mui/material';
import { Visibility, VisibilityOff, CheckCircle, Cancel } from '@mui/icons-material';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { registerUser, verifyOtp, resendOtp } from '../services/api';

// ─── Password strength helpers ──────────────────────────────────
const PASSWORD_CHECKS = [
    { label: 'At least 8 characters', test: (p) => p.length >= 8 },
    { label: 'One uppercase letter', test: (p) => /[A-Z]/.test(p) },
    { label: 'One lowercase letter', test: (p) => /[a-z]/.test(p) },
    { label: 'One digit', test: (p) => /[0-9]/.test(p) },
    { label: 'One special character', test: (p) => /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(p) },
];

const getStrength = (password) => {
    const passed = PASSWORD_CHECKS.filter((c) => c.test(password)).length;
    return Math.round((passed / PASSWORD_CHECKS.length) * 100);
};

const strengthColor = (s) => (s < 40 ? 'error' : s < 80 ? 'warning' : 'success');
const strengthLabel = (s) => (s < 40 ? 'Weak' : s < 80 ? 'Moderate' : 'Strong');

const OTP_COOLDOWN = 30; // seconds

const Register = () => {
    const { user, login, loading: authLoading } = useAuth();
    const navigate = useNavigate();

    // Form state
    const [step, setStep] = useState('form'); // form | otp
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [submitting, setSubmitting] = useState(false);

    // OTP state
    const [otp, setOtp] = useState('');
    const [devOtp, setDevOtp] = useState(''); // dev-mode: OTP shown on screen
    const [cooldown, setCooldown] = useState(0);
    const timerRef = useRef(null);

    useEffect(() => {
        if (!authLoading && user) {
            navigate(user.onboarded ? '/' : '/onboarding', { replace: true });
        }
    }, [user, authLoading, navigate]);

    // Cooldown timer
    useEffect(() => {
        if (cooldown > 0) {
            timerRef.current = setTimeout(() => setCooldown((c) => c - 1), 1000);
        }
        return () => clearTimeout(timerRef.current);
    }, [cooldown]);

    const strength = getStrength(password);
    const passwordsMatch = password && confirmPassword && password === confirmPassword;

    // ─── Submit registration ─────────────────────────────────────
    const handleRegister = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');

        if (!fullName || !email || !password || !confirmPassword) {
            setError('Please fill in all fields');
            return;
        }
        if (password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }
        if (strength < 100) {
            setError('Password does not meet all requirements');
            return;
        }

        setSubmitting(true);
        try {
            const data = await registerUser(email, password, confirmPassword, fullName);
            setSuccess(data.message || 'Verification code sent!');
            setCooldown(data.resend_cooldown_seconds || OTP_COOLDOWN);
            if (data.dev_otp) {
                setDevOtp(data.dev_otp);
                setOtp(data.dev_otp);
            }
            setStep('otp');
        } catch (err) {
            const detail = err.response?.data?.detail;
            if (Array.isArray(detail)) {
                setError(detail.join('. '));
            } else {
                setError(typeof detail === 'string' ? detail : 'Registration failed.');
            }
        } finally {
            setSubmitting(false);
        }
    };

    // ─── Verify OTP ──────────────────────────────────────────────
    const handleVerify = async (e) => {
        e.preventDefault();
        setError('');
        if (!otp) { setError('Enter the verification code'); return; }

        setSubmitting(true);
        try {
            const data = await verifyOtp(email, otp);
            if (data.access_token) {
                login(data.access_token, data.user);
                navigate('/', { replace: true });
            }
        } catch (err) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Verification failed.');
        } finally {
            setSubmitting(false);
        }
    };

    // ─── Resend OTP ──────────────────────────────────────────────
    const handleResend = async () => {
        setError('');
        setSuccess('');
        try {
            const data = await resendOtp(email);
            setSuccess(data.message || 'New code sent!');
            setCooldown(data.resend_cooldown_seconds || OTP_COOLDOWN);
            if (data.dev_otp) {
                setDevOtp(data.dev_otp);
                setOtp(data.dev_otp);
            }
        } catch (err) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Could not resend. Try again later.');
        }
    };

    if (authLoading) return null;

    return (
        <Container maxWidth="sm" sx={{ py: 6 }}>
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
                        Create your account
                    </Typography>
                </Box>

                <CardContent sx={{ p: 4 }}>
                    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                    {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

                    {/* ─── STEP 1: Registration form ─────────────────── */}
                    {step === 'form' && (
                        <Box component="form" onSubmit={handleRegister} noValidate>
                            <TextField
                                fullWidth label="Full Name" value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                                margin="normal" autoFocus
                            />
                            <TextField
                                fullWidth label="Email" type="email" value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                margin="normal" autoComplete="email"
                            />
                            <TextField
                                fullWidth label="Password" value={password}
                                type={showPassword ? 'text' : 'password'}
                                onChange={(e) => setPassword(e.target.value)}
                                margin="normal" autoComplete="new-password"
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

                            {/* Password strength meter */}
                            {password && (
                                <Box sx={{ mt: 1 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                        <LinearProgress
                                            variant="determinate" value={strength}
                                            color={strengthColor(strength)}
                                            sx={{ flexGrow: 1, height: 6, borderRadius: 3 }}
                                        />
                                        <Chip
                                            label={strengthLabel(strength)} size="small"
                                            color={strengthColor(strength)} variant="outlined"
                                        />
                                    </Box>
                                    <List dense sx={{ py: 0 }}>
                                        {PASSWORD_CHECKS.map((c) => (
                                            <ListItem key={c.label} sx={{ py: 0, px: 0 }}>
                                                <ListItemIcon sx={{ minWidth: 28 }}>
                                                    {c.test(password)
                                                        ? <CheckCircle fontSize="small" color="success" />
                                                        : <Cancel fontSize="small" color="error" />}
                                                </ListItemIcon>
                                                <ListItemText
                                                    primary={c.label}
                                                    primaryTypographyProps={{
                                                        variant: 'caption',
                                                        color: c.test(password) ? 'success.main' : 'text.secondary',
                                                    }}
                                                />
                                            </ListItem>
                                        ))}
                                    </List>
                                </Box>
                            )}

                            <TextField
                                fullWidth label="Confirm Password" value={confirmPassword}
                                type={showPassword ? 'text' : 'password'}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                margin="normal" autoComplete="new-password"
                                error={!!confirmPassword && !passwordsMatch}
                                helperText={confirmPassword && !passwordsMatch ? 'Passwords do not match' : ''}
                            />

                            <Button
                                type="submit" fullWidth variant="contained" size="large"
                                disabled={submitting}
                                sx={{ mt: 2, py: 1.5, fontWeight: 700, boxShadow: '0 0 15px rgba(0, 242, 254, 0.4)' }}
                            >
                                {submitting ? <CircularProgress size={22} /> : 'Register'}
                            </Button>

                            <Typography variant="body2" align="center" color="text.secondary" sx={{ mt: 2 }}>
                                Already have an account?{' '}
                                <Typography
                                    component={RouterLink} to="/login"
                                    variant="body2" color="primary" fontWeight={600}
                                    sx={{ textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
                                >
                                    Sign in
                                </Typography>
                            </Typography>
                        </Box>
                    )}

                    {/* ─── STEP 2: OTP verification ──────────────────── */}
                    {step === 'otp' && (
                        <Box component="form" onSubmit={handleVerify} noValidate>
                            <Typography variant="h6" align="center" sx={{ mb: 1 }}>
                                Enter verification code
                            </Typography>
                            <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 3 }}>
                                We sent a 6-digit code to <strong>{email}</strong>
                            </Typography>

                            {/* DEV MODE: show OTP on screen */}
                            {devOtp && (
                                <Alert severity="info" sx={{ mb: 2, textAlign: 'center' }}>
                                    <strong>Dev Mode:</strong> Your OTP is <strong style={{ fontSize: 18, letterSpacing: 4 }}>{devOtp}</strong>
                                </Alert>
                            )}

                            <TextField
                                fullWidth label="Verification Code" value={otp}
                                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                margin="normal" autoFocus
                                inputProps={{ maxLength: 6, style: { letterSpacing: 8, textAlign: 'center', fontSize: 24 } }}
                            />

                            <Button
                                type="submit" fullWidth variant="contained" size="large"
                                disabled={submitting || otp.length < 6}
                                sx={{ mt: 2, py: 1.5, fontWeight: 700, boxShadow: '0 0 15px rgba(0, 242, 254, 0.4)' }}
                            >
                                {submitting ? <CircularProgress size={22} /> : 'Verify & Continue'}
                            </Button>

                            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                                <Button
                                    variant="text" size="small"
                                    disabled={cooldown > 0}
                                    onClick={handleResend}
                                >
                                    {cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend code'}
                                </Button>
                            </Box>

                            <Button
                                variant="text" size="small" fullWidth sx={{ mt: 1 }}
                                onClick={() => { setStep('form'); setOtp(''); setError(''); setSuccess(''); }}
                            >
                                ← Back to registration
                            </Button>
                        </Box>
                    )}
                </CardContent>
            </Card>
        </Container>
    );
};

export default Register;
