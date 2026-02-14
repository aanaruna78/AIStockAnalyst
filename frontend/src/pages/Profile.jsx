import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Card, CardContent, Container, Avatar, Button,
    RadioGroup, FormControlLabel, Radio, Chip, Stack, Divider,
    CircularProgress, Snackbar, Alert, alpha
} from '@mui/material';
import { User, Mail, Shield, Clock, BarChart3, Save, ArrowLeft } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { config } from '../config';
import axios from 'axios';

const SECTORS = ['IT', 'Banking', 'Pharma', 'Auto', 'Energy', 'FMCG', 'Real Estate', 'Metals', 'Infrastructure'];

const Profile = () => {
    const { user, updateUser } = useAuth();
    const navigate = useNavigate();
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState({ open: false, message: '', severity: 'success' });

    const [formData, setFormData] = useState(() => {
        const saved = JSON.parse(localStorage.getItem('user_preferences') || '{}');
        return {
            risk: saved.risk || user?.preferences?.risk_tolerance || 'medium',
            horizon: saved.horizon || user?.preferences?.investment_horizon || 'swing',
            sectors: saved.sectors || user?.preferences?.preferred_sectors || []
        };
    });

    useEffect(() => {
        if (!user) {
            navigate('/onboarding', { replace: true });
        }
    }, [user, navigate]);

    const handleSectorToggle = (sector) => {
        setFormData(prev => ({
            ...prev,
            sectors: prev.sectors.includes(sector)
                ? prev.sectors.filter(s => s !== sector)
                : [...prev.sectors, sector]
        }));
    };

    const handleSave = async () => {
        setSaving(true);
        localStorage.setItem('user_preferences', JSON.stringify(formData));
        try {
            const token = localStorage.getItem('token');
            if (token) {
                await axios.post(`${config.API_BASE_URL}/auth/preferences`, {
                    risk_tolerance: formData.risk,
                    investment_horizon: formData.horizon,
                    preferred_sectors: formData.sectors
                }, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                updateUser({
                    preferences: {
                        risk_tolerance: formData.risk,
                        investment_horizon: formData.horizon,
                        preferred_sectors: formData.sectors
                    },
                    onboarded: true
                });
                setToast({ open: true, message: 'Preferences saved successfully!', severity: 'success' });
            }
        } catch (error) {
            console.error('Failed to save preferences:', error);
            setToast({ open: true, message: 'Failed to save preferences. Try again.', severity: 'error' });
        } finally {
            setSaving(false);
        }
    };

    if (!user) return null;

    const riskLabels = { low: 'Low (Preserve Capital)', medium: 'Medium (Balanced Growth)', high: 'High (Aggressive Returns)' };
    const horizonLabels = { intraday: 'Intraday', swing: 'Swing', long_term: 'Long Term' };

    return (
        <Container maxWidth="md" sx={{ py: 4, pt: 10 }}>
            <Button startIcon={<ArrowLeft size={16} />} onClick={() => navigate('/')} sx={{ mb: 3, fontWeight: 600 }}>
                Back to Dashboard
            </Button>

            {/* Profile Header */}
            <Card sx={{ mb: 3, overflow: 'visible' }}>
                <CardContent sx={{ p: 4 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                        <Avatar
                            src={user.picture || ''}
                            sx={{
                                width: 80, height: 80, fontSize: '2rem', fontWeight: 800,
                                background: user.picture ? 'transparent' : 'linear-gradient(135deg, #38bdf8, #818cf8)',
                                color: '#fff',
                                border: '3px solid',
                                borderColor: 'primary.main',
                            }}
                        >
                            {!user.picture && (user.full_name ? user.full_name[0].toUpperCase() : 'U')}
                        </Avatar>
                        <Box sx={{ flex: 1 }}>
                            <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: '-0.02em' }}>
                                {user.full_name}
                            </Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                                <Mail size={14} />
                                <Typography variant="body2" color="text.secondary">{user.email}</Typography>
                            </Box>
                        </Box>
                    </Box>
                </CardContent>
            </Card>

            {/* Preferences */}
            <Card sx={{ mb: 3 }}>
                <CardContent sx={{ p: 4 }}>
                    <Typography variant="h6" fontWeight={800} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Shield size={20} /> Risk Tolerance
                    </Typography>
                    <RadioGroup
                        value={formData.risk}
                        onChange={(e) => setFormData({ ...formData, risk: e.target.value })}
                    >
                        <FormControlLabel value="low" control={<Radio color="primary" />} label={riskLabels.low} />
                        <FormControlLabel value="medium" control={<Radio color="primary" />} label={riskLabels.medium} />
                        <FormControlLabel value="high" control={<Radio color="primary" />} label={riskLabels.high} />
                    </RadioGroup>

                    <Divider sx={{ my: 3 }} />

                    <Typography variant="h6" fontWeight={800} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Clock size={20} /> Investment Horizon
                    </Typography>
                    <RadioGroup
                        value={formData.horizon}
                        onChange={(e) => setFormData({ ...formData, horizon: e.target.value })}
                    >
                        <FormControlLabel value="intraday" control={<Radio color="primary" />} label="Intraday (Day Trading)" />
                        <FormControlLabel value="swing" control={<Radio color="primary" />} label="Swing (Days to Weeks)" />
                        <FormControlLabel value="long_term" control={<Radio color="primary" />} label="Long Term (Months to Years)" />
                    </RadioGroup>

                    <Divider sx={{ my: 3 }} />

                    <Typography variant="h6" fontWeight={800} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <BarChart3 size={20} /> Preferred Sectors
                    </Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                        {SECTORS.map((sector) => (
                            <Chip
                                key={sector}
                                label={sector}
                                onClick={() => handleSectorToggle(sector)}
                                color={formData.sectors.includes(sector) ? "primary" : "default"}
                                variant={formData.sectors.includes(sector) ? "filled" : "outlined"}
                                sx={{ mb: 1 }}
                            />
                        ))}
                    </Stack>

                    <Box sx={{ mt: 4, textAlign: 'right' }}>
                        <Button
                            variant="contained"
                            startIcon={saving ? <CircularProgress size={16} /> : <Save size={16} />}
                            onClick={handleSave}
                            disabled={saving}
                            sx={{ fontWeight: 700, px: 4, borderRadius: 2 }}
                        >
                            {saving ? 'Saving...' : 'Save Preferences'}
                        </Button>
                    </Box>
                </CardContent>
            </Card>

            <Snackbar
                open={toast.open}
                autoHideDuration={4000}
                onClose={() => setToast(prev => ({ ...prev, open: false }))}
                anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
                <Alert onClose={() => setToast(prev => ({ ...prev, open: false }))} severity={toast.severity} variant="filled">
                    {toast.message}
                </Alert>
            </Snackbar>
        </Container>
    );
};

export default Profile;
