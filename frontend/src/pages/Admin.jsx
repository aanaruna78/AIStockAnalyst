import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Container, Card, CardContent, Avatar, Chip,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Paper, IconButton, Collapse, Stack, Divider, Alert, Grid,
    Tooltip, alpha
} from '@mui/material';
import { Shield, Users, ChevronDown, ChevronUp, Clock, Globe, LogIn, Mail } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Navigate } from 'react-router-dom';
import api from '../services/api';
import AdminModelReport from './AdminModelReport';
import AdminOptionsReport from './AdminOptionsReport';

const Admin = () => {
    const { user } = useAuth();
    const [users, setUsers] = useState([]);
    const [expandedUser, setExpandedUser] = useState(null);
    const [auditLog, setAuditLog] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!user?.is_admin) return;
        const fetchUsers = async () => {
            try {
                const { data } = await api.get('/auth/admin/users');
                setUsers(data);
            } catch {
                setError('Failed to load user list. Admin access required.');
            } finally {
                setLoading(false);
            }
        };
        fetchUsers();
    }, [user?.is_admin]);

    // Guard: only admin
    if (!user?.is_admin) {
        return <Navigate to="/" replace />;
    }

    const fetchAudit = async (email) => {
        if (expandedUser === email) {
            setExpandedUser(null);
            setAuditLog(null);
            return;
        }
        try {
            const { data } = await api.get(`/auth/admin/users/${encodeURIComponent(email)}/audit`);
            setAuditLog(data);
            setExpandedUser(email);
        } catch {
            setError('Failed to load audit log.');
        }
    };

    const formatDate = (iso) => {
        if (!iso) return '—';
        return new Date(iso).toLocaleString('en-IN', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    };

    const timeAgo = (iso) => {
        if (!iso) return '';
        const diff = Date.now() - new Date(iso).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 60) return `${mins}m ago`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `${hrs}h ago`;
        return `${Math.floor(hrs / 24)}d ago`;
    };

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 4 }}>
                <Box sx={{
                    width: 44, height: 44, borderRadius: 2,
                    background: 'linear-gradient(135deg, #ef4444, #f97316)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                    <Shield size={24} color="#fff" />
                </Box>
                <Box>
                    <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: -1 }}>Admin Console</Typography>
                    <Typography variant="subtitle2" color="text.secondary">User management & audit logs</Typography>
                </Box>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }} onClose={() => setError(null)}>{error}</Alert>}

            {/* Stats */}
            <Grid container spacing={2} sx={{ mb: 4 }}>
                <Grid size={{ xs: 12, md: 4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Users size={24} />
                            <Box>
                                <Typography variant="h4" fontWeight={800}>{users.length}</Typography>
                                <Typography variant="caption" color="text.secondary" fontWeight={600}>REGISTERED USERS</Typography>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, md: 4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <LogIn size={24} />
                            <Box>
                                <Typography variant="h4" fontWeight={800}>
                                    {users.reduce((sum, u) => sum + (u.login_count || 0), 0)}
                                </Typography>
                                <Typography variant="caption" color="text.secondary" fontWeight={600}>TOTAL LOGINS</Typography>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, md: 4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Globe size={24} />
                            <Box>
                                <Typography variant="h4" fontWeight={800}>
                                    {users.filter(u => u.google_id).length}
                                </Typography>
                                <Typography variant="caption" color="text.secondary" fontWeight={600}>GOOGLE SSO USERS</Typography>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* User Table */}
            <Typography variant="h6" fontWeight={800} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <Users size={20} /> Registered Users
            </Typography>

            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3 }}>
                <Table>
                    <TableHead sx={{ bgcolor: 'rgba(255,255,255,0.02)' }}>
                        <TableRow>
                            <TableCell width={50} />
                            <TableCell><Typography variant="caption" fontWeight={700}>USER</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>EMAIL</Typography></TableCell>
                            <TableCell align="center"><Typography variant="caption" fontWeight={700}>ROLE</Typography></TableCell>
                            <TableCell align="center"><Typography variant="caption" fontWeight={700}>LOGINS</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>LAST LOGIN</Typography></TableCell>
                            <TableCell><Typography variant="caption" fontWeight={700}>FIRST SEEN</Typography></TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {loading ? (
                            <TableRow>
                                <TableCell colSpan={7} align="center" sx={{ py: 6 }}>Loading...</TableCell>
                            </TableRow>
                        ) : users.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={7} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                                    No users registered yet.
                                </TableCell>
                            </TableRow>
                        ) : (
                            users.map((u) => (
                                <React.Fragment key={u.email}>
                                    <TableRow
                                        hover
                                        onClick={() => fetchAudit(u.email)}
                                        sx={{ cursor: 'pointer', '& > *': { borderBottom: expandedUser === u.email ? 'none' : undefined } }}
                                    >
                                        <TableCell>
                                            <IconButton size="small">
                                                {expandedUser === u.email ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                            </IconButton>
                                        </TableCell>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                                <Avatar src={u.picture || ''} sx={{ width: 32, height: 32, fontSize: '0.8rem' }}>
                                                    {!u.picture && (u.full_name?.[0]?.toUpperCase() || 'U')}
                                                </Avatar>
                                                <Typography variant="body2" fontWeight={700}>{u.full_name || 'Unknown'}</Typography>
                                            </Box>
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" color="text.secondary">{u.email}</Typography>
                                        </TableCell>
                                        <TableCell align="center">
                                            <Chip
                                                label={u.is_admin ? 'ADMIN' : 'USER'}
                                                size="small"
                                                sx={{
                                                    fontWeight: 800,
                                                    fontSize: '0.65rem',
                                                    bgcolor: u.is_admin ? (t) => alpha(t.palette.error.main, 0.1) : (t) => alpha(t.palette.primary.main, 0.1),
                                                    color: u.is_admin ? 'error.main' : 'primary.main',
                                                    borderRadius: 1
                                                }}
                                            />
                                        </TableCell>
                                        <TableCell align="center">
                                            <Typography variant="body2" fontWeight={700}>{u.login_count || 0}</Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Tooltip title={formatDate(u.last_login)}>
                                                <Typography variant="body2" color="text.secondary">
                                                    {timeAgo(u.last_login)}
                                                </Typography>
                                            </Tooltip>
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" color="text.secondary">
                                                {formatDate(u.created_at)}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>

                                    {/* Expanded Audit Log */}
                                    <TableRow>
                                        <TableCell colSpan={7} sx={{ p: 0 }}>
                                            <Collapse in={expandedUser === u.email} timeout="auto" unmountOnExit>
                                                <Box sx={{ p: 3, bgcolor: (t) => alpha(t.palette.primary.main, 0.02) }}>
                                                    <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                                        <Clock size={16} /> Login History — {u.full_name}
                                                    </Typography>

                                                    {auditLog?.login_history?.length > 0 ? (
                                                        <Table size="small">
                                                            <TableHead>
                                                                <TableRow>
                                                                    <TableCell><Typography variant="caption" fontWeight={700}>#</Typography></TableCell>
                                                                    <TableCell><Typography variant="caption" fontWeight={700}>TIMESTAMP</Typography></TableCell>
                                                                    <TableCell><Typography variant="caption" fontWeight={700}>METHOD</Typography></TableCell>
                                                                    <TableCell><Typography variant="caption" fontWeight={700}>IP ADDRESS</Typography></TableCell>
                                                                </TableRow>
                                                            </TableHead>
                                                            <TableBody>
                                                                {[...auditLog.login_history].reverse().map((entry, idx) => (
                                                                    <TableRow key={idx}>
                                                                        <TableCell>
                                                                            <Typography variant="caption" color="text.secondary">
                                                                                {auditLog.login_history.length - idx}
                                                                            </Typography>
                                                                        </TableCell>
                                                                        <TableCell>
                                                                            <Typography variant="body2">{formatDate(entry.timestamp)}</Typography>
                                                                        </TableCell>
                                                                        <TableCell>
                                                                            <Chip
                                                                                label={entry.method?.toUpperCase() || 'UNKNOWN'}
                                                                                size="small"
                                                                                sx={{ fontWeight: 700, fontSize: '0.65rem', borderRadius: 1 }}
                                                                                color={entry.method === 'google' ? 'primary' : 'default'}
                                                                            />
                                                                        </TableCell>
                                                                        <TableCell>
                                                                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                                                                                {entry.ip || '—'}
                                                                            </Typography>
                                                                        </TableCell>
                                                                    </TableRow>
                                                                ))}
                                                            </TableBody>
                                                        </Table>
                                                    ) : (
                                                        <Typography variant="body2" color="text.secondary">No login history available.</Typography>
                                                    )}

                                                    {/* User Preferences */}
                                                    {auditLog?.preferences && auditLog.onboarded && (
                                                        <Box sx={{ mt: 2 }}>
                                                            <Divider sx={{ my: 1.5 }} />
                                                            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>Preferences</Typography>
                                                            <Stack direction="row" spacing={1}>
                                                                <Chip label={`Risk: ${auditLog.preferences.risk_tolerance}`} size="small" variant="outlined" />
                                                                <Chip label={`Horizon: ${auditLog.preferences.investment_horizon}`} size="small" variant="outlined" />
                                                                {auditLog.preferences.preferred_sectors?.length > 0 && (
                                                                    <Chip label={`Sectors: ${auditLog.preferences.preferred_sectors.join(', ')}`} size="small" variant="outlined" />
                                                                )}
                                                            </Stack>
                                                        </Box>
                                                    )}
                                                </Box>
                                            </Collapse>
                                        </TableCell>
                                    </TableRow>
                                </React.Fragment>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

            <Box sx={{ my: 4 }}>
                <AdminModelReport />
            </Box>

            <Box sx={{ my: 4 }}>
                <AdminOptionsReport />
            </Box>
        </Container>
    );
};

export default Admin;
