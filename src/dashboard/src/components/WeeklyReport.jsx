import React from 'react';

const WeeklyReport = () => {
  return (
    <div className="glass-panel" style={{ height: '80vh', display: 'flex', flexDirection: 'column' }}>
      <h2 style={{ marginBottom: '16px' }}>Weekly PDF Report</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>
        Detailed insights on league standings, manager performance, and player stats for this Gameweek.
      </p>
      
      <div style={{ flex: 1, borderRadius: '8px', overflow: 'hidden', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <object 
          data="/gw_report.pdf" 
          type="application/pdf" 
          width="100%" 
          height="100%"
        >
          <div style={{ padding: '24px', textAlign: 'center', background: 'rgba(0, 0, 0, 0.2)' }}>
            <p>Your browser does not support embedding PDFs.</p>
            <a 
              href="/gw_report.pdf" 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ color: 'var(--accent-color)', textDecoration: 'underline', marginTop: '12px', display: 'inline-block' }}
            >
              Download or View the PDF directly
            </a>
          </div>
        </object>
      </div>
    </div>
  );
};

export default WeeklyReport;
