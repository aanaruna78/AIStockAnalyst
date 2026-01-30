import { createTheme } from '@mui/material/styles';

export const getDesignTokens = (mode) => ({
    palette: {
        mode,
        ...(mode === 'light' ? {
            // Light Mode
            primary: {
                main: '#00c3cc', // Slightly deeper teal for readability
                light: '#4facfe',
                dark: '#008a91',
                contrastText: '#fff',
            },
            secondary: {
                main: '#7000ff',
                light: '#9d4dff',
                dark: '#5200ba',
            },
            background: {
                default: '#f8fafc', // Very light grey/blue
                paper: '#ffffff',
            },
            text: {
                primary: '#0f172a',
                secondary: '#64748b',
            },
        } : {
            // Dark Mode
            primary: {
                main: '#00f2fe',
                light: '#4facfe',
                dark: '#00c3cc',
                contrastText: '#000',
            },
            secondary: {
                main: '#c084fc',
                light: '#e9d5ff',
                dark: '#9333ea',
            },
            background: {
                default: '#0a0e17',
                paper: '#161d2a',
            },
            text: {
                primary: '#ffffff',
                secondary: 'rgba(255, 255, 255, 0.7)',
            },
        }),
    },
    typography: {
        fontFamily: '"Outfit", "Inter", "Roboto", sans-serif',
        h1: { fontWeight: 700, letterSpacing: '-0.02em' },
        h2: { fontWeight: 700, letterSpacing: '-0.01em' },
        h3: { fontWeight: 600 },
        button: { textTransform: 'none', fontWeight: 600 },
    },
    shape: {
        borderRadius: 12,
    },
    components: {
        MuiButton: {
            styleOverrides: {
                root: {
                    borderRadius: 8,
                    padding: '8px 20px',
                    transition: 'all 0.2s ease-in-out',
                },
            },
        },
        MuiCard: {
            styleOverrides: {
                root: ({ ownerState, theme }) => ({
                    backgroundImage: mode === 'dark'
                        ? 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 100%)'
                        : 'none',
                    backdropFilter: mode === 'dark' ? 'blur(10px)' : 'none',
                    border: mode === 'dark' ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.05)',
                    boxShadow: mode === 'dark'
                        ? '0 8px 32px 0 rgba(0, 0, 0, 0.37)'
                        : '0 4px 12px 0 rgba(0, 0, 0, 0.05)',
                }),
            },
        },
        MuiAppBar: {
            styleOverrides: {
                root: {
                    backgroundColor: mode === 'dark' ? 'rgba(10, 14, 23, 0.8)' : 'rgba(255, 255, 255, 0.8)',
                    backdropFilter: 'blur(20px)',
                    borderBottom: mode === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.05)',
                    color: mode === 'dark' ? '#fff' : '#0f172a',
                },
            },
        },
    },
});

const theme = createTheme(getDesignTokens('dark')); // Default fallback
export default theme;
