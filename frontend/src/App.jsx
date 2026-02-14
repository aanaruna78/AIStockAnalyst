import React, { useState, useEffect, useRef, useCallback } from 'react';
import { CssBaseline, Box, Snackbar, Alert as MuiAlert } from '@mui/material';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { ThemeContextProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import Header from './components/Header';
import '@fontsource/inter';
import '@fontsource/outfit';

import Dashboard from './pages/DashboardNew';
import Onboarding from './pages/Onboarding';
import RecommendationDetail from './pages/RecommendationDetailNew';
import Watchlist from './pages/WatchlistNew';
import Alerts from './pages/AlertsNew';
import Portfolio from './pages/Portfolio';
import AgentDashboard from './pages/AgentDashboard';
import Profile from './pages/Profile';
import { fetchAlerts } from './services/api';
import { isBullish } from './utils/formatters';

// Auth guard — redirects to /onboarding if not logged in
const RequireAuth = ({ children }) => {
    const { user, loading } = useAuth();
    const location = useLocation();

    if (loading) return null; // or a loading spinner
    if (!user) return <Navigate to="/onboarding" state={{ from: location }} replace />;
    return children;
};

function App() {
  const [toast, setToast] = useState({ open: false, message: '', severity: 'info' });
  const prevIdsRef = useRef(new Set());
  const initialLoadRef = useRef(true);

  // Global alert polling — shows toasts on any page
  const pollAlerts = useCallback(async () => {
    try {
      const data = await fetchAlerts();
      const ids = new Set((data || []).map(a => a.id));

      if (!initialLoadRef.current && prevIdsRef.current.size > 0) {
        const newOnes = (data || []).filter(a => !prevIdsRef.current.has(a.id));
        if (newOnes.length > 0) {
          const first = newOnes[0];
          const bull = isBullish(first.direction);
          setToast({
            open: true,
            message: newOnes.length === 1
              ? `${bull ? '🟢' : '🔴'} New ${bull ? 'LONG' : 'SHORT'} signal: ${first.symbol} — Conviction ${(first.conviction || 0).toFixed(1)}%`
              : `📢 ${newOnes.length} new signals detected`,
            severity: bull ? 'success' : 'error'
          });
        }
      }
      initialLoadRef.current = false;
      prevIdsRef.current = ids;
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    pollAlerts();
    const iv = setInterval(pollAlerts, 30000);
    return () => clearInterval(iv);
  }, [pollAlerts]);

  return (
    <ThemeContextProvider>
      <CssBaseline />
      <AuthProvider>
        <Router>
          <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', color: 'text.primary' }}>
            <Header />
            <Routes>
              <Route path="/onboarding" element={<Onboarding />} />
              <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
              <Route path="/recommendation/:id" element={<RequireAuth><RecommendationDetail /></RequireAuth>} />
              <Route path="/watchlist" element={<RequireAuth><Watchlist /></RequireAuth>} />
              <Route path="/alerts" element={<RequireAuth><Alerts /></RequireAuth>} />
              <Route path="/portfolio" element={<RequireAuth><Portfolio /></RequireAuth>} />
              <Route path="/agent" element={<RequireAuth><AgentDashboard /></RequireAuth>} />
              <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
            </Routes>
          </Box>

          {/* Global toast for new alerts */}
          <Snackbar
            open={toast.open}
            autoHideDuration={6000}
            onClose={() => setToast(prev => ({ ...prev, open: false }))}
            anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            <MuiAlert
              onClose={() => setToast(prev => ({ ...prev, open: false }))}
              severity={toast.severity}
              variant="filled"
              elevation={8}
              sx={{ fontWeight: 600, minWidth: 300, fontSize: '0.85rem' }}
            >
              {toast.message}
            </MuiAlert>
          </Snackbar>
        </Router>
      </AuthProvider>
    </ThemeContextProvider>
  );
}

export default App;
