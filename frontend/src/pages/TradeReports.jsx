import { useState, useEffect } from 'react';
import { fetchTradeReport } from '../services/api';

export default function TradeReports() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [error, setError] = useState('');

  const loadReport = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchTradeReport(startDate || null, endDate || null);
      setReport(data);
    } catch {
      setError('Failed to load trade report');
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchTradeReport(null, null)
      .then(data => { setReport(data); setLoading(false); })
      .catch(() => { setError('Failed to load trade report'); setLoading(false); });
  }, []);

  const pnlColor = (val) => val > 0 ? '#27c93f' : val < 0 ? '#ff5f56' : '#888';

  return (
    <div style={{ padding: '24px', maxWidth: 1200, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 16 }}>Trade Performance Report</h2>

      {/* Date Range Picker */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 24, flexWrap: 'wrap' }}>
        <label>
          Start Date:
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
            style={{ marginLeft: 8, padding: '6px 10px', borderRadius: 6, border: '1px solid #444', background: '#1a1a2e', color: '#fff' }} />
        </label>
        <label>
          End Date:
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
            style={{ marginLeft: 8, padding: '6px 10px', borderRadius: 6, border: '1px solid #444', background: '#1a1a2e', color: '#fff' }} />
        </label>
        <button onClick={loadReport}
          style={{ padding: '8px 20px', borderRadius: 6, background: '#00e5ff', color: '#000', border: 'none', fontWeight: 600, cursor: 'pointer' }}>
          Apply Filter
        </button>
        <button onClick={() => { setStartDate(''); setEndDate(''); setTimeout(loadReport, 50); }}
          style={{ padding: '8px 16px', borderRadius: 6, background: '#333', color: '#fff', border: '1px solid #555', cursor: 'pointer' }}>
          Reset
        </button>
      </div>

      {loading && <p>Loading...</p>}
      {error && <p style={{ color: '#ff5f56' }}>{error}</p>}

      {report && !loading && (
        <>
          {/* Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16, marginBottom: 32 }}>
            <SummaryCard label="Total Trades" value={report.total_trades} />
            <SummaryCard label="Winners" value={report.winners} color="#27c93f" />
            <SummaryCard label="Losers" value={report.losers} color="#ff5f56" />
            <SummaryCard label="Win Rate" value={`${report.win_rate}%`} color={report.win_rate >= 50 ? '#27c93f' : '#ff5f56'} />
            <SummaryCard label="Total P&L" value={`₹${report.total_pnl?.toLocaleString()}`} color={pnlColor(report.total_pnl)} />
            <SummaryCard label="Avg Win" value={`₹${report.avg_win?.toLocaleString()}`} color="#27c93f" />
            <SummaryCard label="Avg Loss" value={`₹${report.avg_loss?.toLocaleString()}`} color="#ff5f56" />
            <SummaryCard label="Profit Factor" value={report.profit_factor} color="#00e5ff" />
          </div>

          {/* Trade Table */}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #333' }}>
                  <th style={thStyle}>Symbol</th>
                  <th style={thStyle}>Type</th>
                  <th style={thStyle}>Entry</th>
                  <th style={thStyle}>Exit</th>
                  <th style={thStyle}>Qty</th>
                  <th style={thStyle}>P&L</th>
                  <th style={thStyle}>P&L %</th>
                  <th style={thStyle}>Entry Time</th>
                  <th style={thStyle}>Exit Time</th>
                </tr>
              </thead>
              <tbody>
                {report.trades?.map((t, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                    <td style={tdStyle}>{t.symbol}</td>
                    <td style={{ ...tdStyle, color: t.type === 'BUY' ? '#27c93f' : '#ff5f56' }}>{t.type}</td>
                    <td style={tdStyle}>₹{t.entry_price?.toFixed(2)}</td>
                    <td style={tdStyle}>{t.exit_price ? `₹${t.exit_price.toFixed(2)}` : '-'}</td>
                    <td style={tdStyle}>{t.quantity}</td>
                    <td style={{ ...tdStyle, color: pnlColor(t.pnl), fontWeight: 600 }}>
                      ₹{(t.pnl || 0).toFixed(2)}
                    </td>
                    <td style={{ ...tdStyle, color: pnlColor(t.pnl_percent) }}>
                      {(t.pnl_percent || 0).toFixed(1)}%
                    </td>
                    <td style={tdStyle}>{t.entry_time ? new Date(t.entry_time).toLocaleString('en-IN') : '-'}</td>
                    <td style={tdStyle}>{t.exit_time ? new Date(t.exit_time).toLocaleString('en-IN') : '-'}</td>
                  </tr>
                ))}
                {report.trades?.length === 0 && (
                  <tr><td colSpan={9} style={{ ...tdStyle, textAlign: 'center', color: '#888' }}>No trades found for selected period</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function SummaryCard({ label, value, color = '#fff' }) {
  return (
    <div style={{ background: '#1a1a2e', borderRadius: 10, padding: '16px 20px', border: '1px solid #333' }}>
      <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

const thStyle = { textAlign: 'left', padding: '10px 8px', color: '#888', fontWeight: 500 };
const tdStyle = { padding: '10px 8px', color: '#ccc' };
