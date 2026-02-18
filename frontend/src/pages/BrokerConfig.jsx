import { useState, useEffect } from 'react';
import { fetchBrokerConfig, updateBrokerConfig } from '../services/api';

export default function BrokerConfig() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  // Form state
  const [brokerType, setBrokerType] = useState('none');
  const [isActive, setIsActive] = useState(false);
  const [dhanClientId, setDhanClientId] = useState('');
  const [dhanToken, setDhanToken] = useState('');
  const [angelApiKey, setAngelApiKey] = useState('');
  const [angelClientId, setAngelClientId] = useState('');
  const [angelPassword, setAngelPassword] = useState('');
  const [angelTotp, setAngelTotp] = useState('');

  const applyConfig = (data) => {
    setConfig(data);
    setBrokerType(data.broker_type || 'none');
    setIsActive(data.is_active || false);
    setLoading(false);
  };

  useEffect(() => {
    fetchBrokerConfig()
      .then(applyConfig)
      .catch(() => { setMessage('Failed to load broker config'); setLoading(false); });
  }, []);

  const loadConfig = async () => {
    try {
      const data = await fetchBrokerConfig();
      applyConfig(data);
    } catch {
      setMessage('Failed to load broker config');
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    try {
      const payload = {
        broker_type: brokerType,
        is_active: isActive,
        dhan_client_id: dhanClientId || null,
        dhan_access_token: dhanToken || null,
        angelone_api_key: angelApiKey || null,
        angelone_client_id: angelClientId || null,
        angelone_password: angelPassword || null,
        angelone_totp_secret: angelTotp || null,
      };
      await updateBrokerConfig(payload);
      setMessage('Broker config saved successfully!');
      await loadConfig();
    } catch {
      setMessage('Failed to save broker config');
    }
    setSaving(false);
  };

  if (loading) return <p style={{ padding: 24 }}>Loading broker configuration...</p>;

  return (
    <div style={{ padding: 24, maxWidth: 600, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 8 }}>Broker Configuration</h2>
      <p style={{ color: '#888', marginBottom: 24, fontSize: 14 }}>
        Configure your broker API for live trading. Paper trading runs in parallel regardless of this setting.
      </p>

      {/* Current Status */}
      {config && (
        <div style={{ background: '#1a1a2e', borderRadius: 10, padding: 16, marginBottom: 24, border: '1px solid #333' }}>
          <div style={{ fontSize: 13, color: '#888' }}>Current Status</div>
          <div style={{ display: 'flex', gap: 20, marginTop: 8 }}>
            <span>Broker: <b style={{ color: '#00e5ff' }}>{config.broker_type?.toUpperCase()}</b></span>
            <span>Active: <b style={{ color: config.is_active ? '#27c93f' : '#ff5f56' }}>{config.is_active ? 'YES' : 'NO'}</b></span>
            {config.dhan_configured && <span style={{ color: '#27c93f' }}>✓ Dhan</span>}
            {config.angelone_configured && <span style={{ color: '#27c93f' }}>✓ AngelOne</span>}
          </div>
        </div>
      )}

      {/* Broker Type */}
      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>Broker Type</label>
        <select value={brokerType} onChange={e => setBrokerType(e.target.value)} style={inputStyle}>
          <option value="none">None (Paper Trading Only)</option>
          <option value="dhan">Dhan</option>
          <option value="angelone">AngelOne</option>
        </select>
      </div>

      {/* Dhan Config */}
      {brokerType === 'dhan' && (
        <div style={{ background: '#1a1a2e', borderRadius: 10, padding: 20, marginBottom: 20, border: '1px solid #333' }}>
          <h4 style={{ margin: '0 0 12px', color: '#00e5ff' }}>Dhan API Credentials</h4>
          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Client ID</label>
            <input type="text" value={dhanClientId} onChange={e => setDhanClientId(e.target.value)}
              placeholder="Your Dhan Client ID" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Access Token</label>
            <input type="password" value={dhanToken} onChange={e => setDhanToken(e.target.value)}
              placeholder="Your Dhan Access Token" style={inputStyle} />
          </div>
        </div>
      )}

      {/* AngelOne Config */}
      {brokerType === 'angelone' && (
        <div style={{ background: '#1a1a2e', borderRadius: 10, padding: 20, marginBottom: 20, border: '1px solid #333' }}>
          <h4 style={{ margin: '0 0 12px', color: '#ffbd2e' }}>AngelOne API Credentials</h4>
          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>API Key</label>
            <input type="text" value={angelApiKey} onChange={e => setAngelApiKey(e.target.value)}
              placeholder="AngelOne API Key" style={inputStyle} />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Client ID</label>
            <input type="text" value={angelClientId} onChange={e => setAngelClientId(e.target.value)}
              placeholder="AngelOne Client ID" style={inputStyle} />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Password</label>
            <input type="password" value={angelPassword} onChange={e => setAngelPassword(e.target.value)}
              placeholder="Trading Password" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>TOTP Secret</label>
            <input type="password" value={angelTotp} onChange={e => setAngelTotp(e.target.value)}
              placeholder="TOTP Secret for 2FA" style={inputStyle} />
          </div>
        </div>
      )}

      {/* Enable Live Trading */}
      {brokerType !== 'none' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
          <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)}
            style={{ width: 18, height: 18 }} />
          <label style={{ color: isActive ? '#27c93f' : '#888' }}>
            Enable Live Trading (paper trading continues in parallel)
          </label>
        </div>
      )}

      <button onClick={handleSave} disabled={saving}
        style={{ padding: '10px 24px', borderRadius: 8, background: '#00e5ff', color: '#000', border: 'none', fontWeight: 600, cursor: 'pointer', opacity: saving ? 0.5 : 1 }}>
        {saving ? 'Saving...' : 'Save Configuration'}
      </button>

      {message && (
        <p style={{ marginTop: 16, color: message.includes('success') ? '#27c93f' : '#ff5f56', fontSize: 14 }}>
          {message}
        </p>
      )}
    </div>
  );
}

const labelStyle = { display: 'block', fontSize: 12, color: '#888', marginBottom: 4 };
const inputStyle = {
  width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #444',
  background: '#0f0f23', color: '#fff', fontSize: 14, boxSizing: 'border-box'
};
