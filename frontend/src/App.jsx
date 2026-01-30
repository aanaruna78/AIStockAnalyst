import React from 'react';
import { CssBaseline, Box } from '@mui/material';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeContextProvider } from './context/ThemeContext';
import Header from './components/Header';
import '@fontsource/inter';
import '@fontsource/outfit';

import Dashboard from './pages/Dashboard';
import Onboarding from './pages/Onboarding';
import RecommendationDetail from './pages/RecommendationDetail';
import Watchlist from './pages/Watchlist';
import Alerts from './pages/Alerts';
import Portfolio from './pages/Portfolio';

function App() {
  return (
    <ThemeContextProvider>
      <CssBaseline />
      <Router>
        <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', color: 'text.primary' }}>
          <Header />
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/recommendation/:id" element={<RecommendationDetail />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/portfolio" element={<Portfolio />} />
          </Routes>
        </Box>
      </Router>
    </ThemeContextProvider>
  );
}

export default App;
