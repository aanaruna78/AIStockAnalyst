export const getDesignTokens = (mode) => ({
    palette: {
        mode,
        ...(mode === 'light' ? {
            primary: { main: '#0ea5e9', light: '#38bdf8', dark: '#0284c7', contrastText: '#fff' },
            secondary: { main: '#6366f1', light: '#818cf8', dark: '#4f46e5' },
            success: { main: '#10b981', light: '#34d399', dark: '#059669' },
            error: { main: '#ef4444', light: '#f87171', dark: '#dc2626' },
            warning: { main: '#f59e0b', light: '#fbbf24', dark: '#d97706' },
            background: { default: '#f8fafc', paper: '#ffffff', card: '#ffffff', elevated: '#f1f5f9' },
            text: { primary: '#0f172a', secondary: '#64748b', disabled: '#94a3b8' },
            divider: 'rgba(0,0,0,0.06)',
        } : {
            primary: { main: '#38bdf8', light: '#7dd3fc', dark: '#0ea5e9', contrastText: '#0c1222' },
            secondary: { main: '#818cf8', light: '#a5b4fc', dark: '#6366f1' },
            success: { main: '#10b981', light: '#34d399', dark: '#059669' },
            error: { main: '#ef4444', light: '#f87171', dark: '#dc2626' },
            warning: { main: '#f59e0b', light: '#fbbf24', dark: '#d97706' },
            background: { default: '#0c1222', paper: '#131c31', card: '#162036', elevated: '#1a2744' },
            text: { primary: '#f1f5f9', secondary: '#94a3b8', disabled: '#475569' },
            divider: 'rgba(255,255,255,0.06)',
        }),
    },
    typography: {
        fontFamily: '"Inter", "Outfit", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        h1: { fontWeight: 800, letterSpacing: '-0.025em', fontSize: '2.25rem' },
        h2: { fontWeight: 700, letterSpacing: '-0.02em', fontSize: '1.875rem' },
        h3: { fontWeight: 700, letterSpacing: '-0.015em', fontSize: '1.5rem' },
        h4: { fontWeight: 700, letterSpacing: '-0.01em', fontSize: '1.25rem' },
        h5: { fontWeight: 600, fontSize: '1.125rem' },
        h6: { fontWeight: 600, fontSize: '1rem' },
        subtitle1: { fontWeight: 500, fontSize: '0.9375rem' },
        subtitle2: { fontWeight: 600, fontSize: '0.8125rem', letterSpacing: '0.02em' },
        body1: { fontSize: '0.9375rem', lineHeight: 1.6 },
        body2: { fontSize: '0.8125rem', lineHeight: 1.5 },
        caption: { fontSize: '0.6875rem', letterSpacing: '0.03em' },
        overline: { fontSize: '0.625rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' },
        button: { textTransform: 'none', fontWeight: 600, letterSpacing: '0.01em' },
    },
    shape: { borderRadius: 12 },
    components: {
        MuiCssBaseline: {
            styleOverrides: {
                body: {
                    scrollbarWidth: 'thin',
                    '&::-webkit-scrollbar': { width: '6px', height: '6px' },
                    '&::-webkit-scrollbar-thumb': {
                        borderRadius: 3,
                        backgroundColor: mode === 'dark' ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)',
                    },
                    '&::-webkit-scrollbar-track': { backgroundColor: 'transparent' },
                },
            },
        },
        MuiButton: {
            defaultProps: { disableElevation: true },
            styleOverrides: {
                root: { borderRadius: 8, padding: '8px 18px', fontWeight: 600, transition: 'all 0.15s ease' },
                contained: {
                    '&:hover': { transform: 'translateY(-1px)', boxShadow: mode === 'dark' ? '0 4px 12px rgba(56,189,248,0.3)' : '0 4px 12px rgba(14,165,233,0.3)' },
                },
                outlined: { borderWidth: '1.5px', '&:hover': { borderWidth: '1.5px' } },
            },
        },
        MuiCard: {
            defaultProps: { elevation: 0 },
            styleOverrides: {
                root: {
                    borderRadius: 16,
                    border: mode === 'dark' ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)',
                    backgroundColor: mode === 'dark' ? '#162036' : '#ffffff',
                    transition: 'all 0.2s ease',
                },
            },
        },
        MuiAppBar: {
            defaultProps: { elevation: 0 },
            styleOverrides: {
                root: {
                    backgroundColor: mode === 'dark' ? 'rgba(12, 18, 34, 0.85)' : 'rgba(255, 255, 255, 0.85)',
                    backdropFilter: 'blur(20px) saturate(180%)',
                    borderBottom: mode === 'dark' ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)',
                    color: mode === 'dark' ? '#f1f5f9' : '#0f172a',
                },
            },
        },
        MuiChip: {
            styleOverrides: {
                root: { fontWeight: 600, letterSpacing: '0.02em' },
                sizeSmall: { height: 24, fontSize: '0.6875rem' },
            },
        },
        MuiTooltip: {
            defaultProps: { arrow: true },
            styleOverrides: {
                tooltip: { borderRadius: 8, fontSize: '0.75rem', fontWeight: 500, padding: '8px 12px', backgroundColor: '#1e293b', color: '#f1f5f9' },
                arrow: { color: '#1e293b' },
            },
        },
        MuiDialog: {
            styleOverrides: {
                paper: { borderRadius: 20, border: mode === 'dark' ? '1px solid rgba(255,255,255,0.06)' : 'none', boxShadow: '0 24px 48px rgba(0,0,0,0.2)' },
            },
        },
        MuiTableCell: {
            styleOverrides: {
                root: { borderBottom: mode === 'dark' ? '1px solid rgba(255,255,255,0.04)' : '1px solid rgba(0,0,0,0.04)', padding: '12px 16px' },
                head: { fontWeight: 700, fontSize: '0.6875rem', letterSpacing: '0.05em', textTransform: 'uppercase', color: '#64748b' },
            },
        },
        MuiPaper: { defaultProps: { elevation: 0 }, styleOverrides: { root: { backgroundImage: 'none' } } },
        MuiLinearProgress: { styleOverrides: { root: { borderRadius: 4, height: 6 }, bar: { borderRadius: 4 } } },
        MuiTab: { styleOverrides: { root: { fontWeight: 600, textTransform: 'none', minHeight: 44 } } },
    },
});

export default getDesignTokens;
