import React, { useState, useEffect } from 'react';
import {
    Box, Stepper, Step, StepLabel, Button, Typography,
    RadioGroup, FormControlLabel, Radio,
    Card, CardContent, Container, Chip, Stack, CircularProgress
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { config } from '../config';
import axios from 'axios';

const PREFERENCE_STEPS = ['Risk Profile', 'Investment Horizon', 'Market Preferences'];

const Onboarding = () => {
    const { user, loading: authLoading } = useAuth();
    const [activeStep, setActiveStep] = useState(0);
    const [saving, setSaving] = useState(false);
    const [formData, setFormData] = useState({
        risk: 'medium',
        horizon: 'swing',
        sectors: []
    });
    const navigate = useNavigate();

    // If user is already logged in and onboarded, go to dashboard
    useEffect(() => {
        if (!authLoading && user && user.onboarded) {
            navigate('/', { replace: true });
        }
    }, [user, authLoading, navigate]);

    // Redirect unauthenticated users to login
    useEffect(() => {
        if (!authLoading && !user) {
            navigate('/login', { replace: true });
        }
    }, [user, authLoading, navigate]);

    const handleNext = async () => {
        if (activeStep === PREFERENCE_STEPS.length - 1) {
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
                }
            } catch (error) {
                console.error('Failed to save preferences:', error);
            } finally {
                setSaving(false);
            }
            navigate('/', { replace: true });
        } else {
            setActiveStep((prev) => prev + 1);
        }
    };

    const handleBack = () => setActiveStep((prev) => prev - 1);

    const handleSectorToggle = (sector) => {
        setFormData(prev => ({
            ...prev,
            sectors: prev.sectors.includes(sector)
                ? prev.sectors.filter(s => s !== sector)
                : [...prev.sectors, sector]
        }));
    };

    // Redirect unauthenticated to login
    if (!user) return null;

    // Show preference steps for new (not-yet-onboarded) users
    return (
        <Container maxWidth="sm" sx={{ py: 8 }}>
            <Card>
                <CardContent sx={{ p: 4 }}>
                    <Typography variant="h4" component="h1" align="center" gutterBottom color="primary" fontWeight={800}>
                        Welcome, {user.full_name?.split(' ')[0] || 'there'}!
                    </Typography>
                    <Typography variant="body1" align="center" color="text.secondary" sx={{ mb: 4 }}>
                        Let's tailor your experience for high-conviction signals.
                    </Typography>

                    <Stepper activeStep={activeStep} alternativeLabel>
                        {PREFERENCE_STEPS.map((label) => (
                            <Step key={label}>
                                <StepLabel>{label}</StepLabel>
                            </Step>
                        ))}
                    </Stepper>

                    <Box sx={{ mt: 4 }}>
                        {activeStep === 0 && (
                            <Box>
                                <Typography variant="h6" gutterBottom>How much risk can you handle?</Typography>
                                <RadioGroup
                                    value={formData.risk}
                                    onChange={(e) => setFormData({ ...formData, risk: e.target.value })}
                                >
                                    <FormControlLabel value="low" control={<Radio color="primary" />} label="Low (Preserve Capital)" />
                                    <FormControlLabel value="medium" control={<Radio color="primary" />} label="Medium (Balanced Growth)" />
                                    <FormControlLabel value="high" control={<Radio color="primary" />} label="High (Aggressive Returns)" />
                                </RadioGroup>
                            </Box>
                        )}
                        {activeStep === 1 && (
                            <Box>
                                <Typography variant="h6" gutterBottom>What is your usual holding period?</Typography>
                                <RadioGroup
                                    value={formData.horizon}
                                    onChange={(e) => setFormData({ ...formData, horizon: e.target.value })}
                                >
                                    <FormControlLabel value="intraday" control={<Radio color="primary" />} label="Intraday (Day Trading)" />
                                    <FormControlLabel value="swing" control={<Radio color="primary" />} label="Swing (Days to Weeks)" />
                                    <FormControlLabel value="long_term" control={<Radio color="primary" />} label="Long Term (Months to Years)" />
                                </RadioGroup>
                            </Box>
                        )}
                        {activeStep === 2 && (
                            <Box>
                                <Typography variant="h6" gutterBottom>Select sectors you are interested in:</Typography>
                                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
                                    {['IT', 'Banking', 'Pharma', 'Auto', 'Energy', 'FMCG', 'Real Estate', 'Metals', 'Infrastructure'].map((sector) => (
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
                            </Box>
                        )}
                    </Box>

                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 6 }}>
                        <Button disabled={activeStep === 0} onClick={handleBack} variant="outlined">Back</Button>
                        <Button
                            variant="contained"
                            onClick={handleNext}
                            disabled={saving}
                            startIcon={saving ? <CircularProgress size={16} /> : null}
                            sx={{ boxShadow: '0 0 15px rgba(0, 242, 254, 0.4)' }}
                        >
                            {activeStep === PREFERENCE_STEPS.length - 1 ? 'Get Started' : 'Next'}
                        </Button>
                    </Box>
                </CardContent>
            </Card>
        </Container>
    );
};

export default Onboarding;
