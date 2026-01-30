import React, { useState } from 'react';
import {
    Box, Stepper, Step, StepLabel, Button, Typography,
    FormControl, FormLabel, RadioGroup, FormControlLabel, Radio,
    Card, CardContent, Container, Slider, Chip, Stack, Divider
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import axios from 'axios';

const steps = ['Authentication', 'Risk Profile', 'Investment Horizon', 'Market Preferences'];

const Onboarding = () => {
    const [activeStep, setActiveStep] = useState(0);
    const [user, setUser] = useState(null);
    const [formData, setFormData] = useState({
        risk: 'medium',
        horizon: 'swing',
        sectors: []
    });
    const navigate = useNavigate();

    const handleGoogleSuccess = async (credentialResponse) => {
        try {
            const response = await axios.post(`${import.meta.env.VITE_API_URL}/api/v1/auth/google`, {
                token: credentialResponse.credential
            });

            if (response.data.access_token) {
                localStorage.setItem('token', response.data.access_token);
                setUser(response.data.user || { name: 'User' });
                setActiveStep(1); // Move to next step after successful login
            }
        } catch (error) {
            console.error('Google Login Error:', error);
            alert('Authentication failed. Please try again.');
        }
    };

    const handleNext = async () => {
        if (activeStep === steps.length - 1) {
            // Finalize onboarding
            localStorage.setItem('user_preferences', JSON.stringify(formData));
            try {
                const token = localStorage.getItem('token');
                if (token) {
                    await axios.post(`${import.meta.env.VITE_API_URL}/api/v1/auth/preferences`, {
                        risk_tolerance: formData.risk,
                        investment_horizon: formData.horizon,
                        preferred_sectors: formData.sectors
                    }, {
                        headers: { Authorization: `Bearer ${token}` }
                    });
                }
            } catch (error) {
                console.error('Failed to save preferences:', error);
            }
            navigate('/');
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

    const renderStepContent = (step) => {
        switch (step) {
            case 0:
                return (
                    <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                        <Typography variant="h6" align="center">Sign in to sync your portfolio and signals</Typography>
                        <GoogleLogin
                            onSuccess={handleGoogleSuccess}
                            onError={() => console.log('Login Failed')}
                            useOneTap
                            theme="filled_blue"
                            shape="pill"
                        />
                        <Divider sx={{ width: '100%', my: 2 }}>OR</Divider>
                        <Button variant="text" onClick={() => setActiveStep(1)}>Skip for now</Button>
                    </Box>
                );
            case 1:
                return (
                    <Box sx={{ mt: 3 }}>
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
                );
            case 2:
                return (
                    <Box sx={{ mt: 3 }}>
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
                );
            case 3:
                return (
                    <Box sx={{ mt: 3 }}>
                        <Typography variant="h6" gutterBottom>Select sectors you are interested in:</Typography>
                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
                            {['IT', 'Banking', 'Pharma', 'Auto', 'Energy', 'FMCG', 'Real Estate'].map((sector) => (
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
                );
            default:
                return null;
        }
    };

    return (
        <Container maxWidth="sm" sx={{ py: 8 }}>
            <Card>
                <CardContent sx={{ p: 4 }}>
                    <Typography variant="h4" component="h1" align="center" gutterBottom color="primary">
                        Welcome to SignalForge
                    </Typography>
                    <Typography variant="body1" align="center" color="text.secondary" sx={{ mb: 4 }}>
                        Tailor your experience for high-conviction signals.
                    </Typography>

                    <Stepper activeStep={activeStep} alternativeLabel>
                        {steps.map((label) => (
                            <Step key={label}>
                                <StepLabel>{label}</StepLabel>
                            </Step>
                        ))}
                    </Stepper>

                    {renderStepContent(activeStep)}

                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 6 }}>
                        <Button
                            disabled={activeStep === 0}
                            onClick={handleBack}
                            variant="outlined"
                        >
                            Back
                        </Button>
                        <Button
                            variant="contained"
                            disabled={activeStep === 0 && !user}
                            onClick={handleNext}
                            sx={{ boxShadow: '0 0 15px rgba(0, 242, 254, 0.4)' }}
                        >
                            {activeStep === steps.length - 1 ? 'Get Started' : 'Next'}
                        </Button>
                    </Box>
                </CardContent>
            </Card>
        </Container>
    );
};

export default Onboarding;
