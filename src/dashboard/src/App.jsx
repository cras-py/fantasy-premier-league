import { useState } from 'react'
import './index.css'

// Import data directly so Vite bundles it and we don't rely on fetch() routing
import agentDataRaw from '../../../data/processed/agent_recommendations.json'
import userEntryRaw from '../../../data/processed/user_entry.json'
import userLeagueRaw from '../../../data/processed/user_league.json'

function App() {
  const [activeTab, setActiveTab] = useState('team')

  const agentData = agentDataRaw || null;
  const userEntry = userEntryRaw?.entry || {};
  const userHistory = userEntryRaw?.history || {};
  
  const teamName = userEntry.name || "Your Team";
  const managerName = `${userEntry.player_first_name || ""} ${userEntry.player_last_name || ""}`.trim() || "You";
  const overallPoints = userEntry.summary_overall_points || 0;
  const gwPoints = userEntry.summary_event_points || 0;
  const teamValue = ((userEntry.last_deadline_value || 0) / 10).toFixed(1);
  
  const standings = userLeagueRaw?.standings?.results || [];
  
  const squad = userEntryRaw?.squad || [];
  const topPerformers = [...squad]
    .filter(p => p.multiplier > 0) // only starting 11
    .sort((a, b) => b.event_points - a.event_points)
    .slice(0, 2);

  return (
    <div className="app-container">
      <header className="header animate-fade-in">
        <div>
          <h1 className="text-gradient" style={{ fontSize: '2.5rem' }}>FPL Intelligence</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Advanced analytics & agentic recommendations</p>
        </div>
        <div className="nav-tabs">
          <button 
            className={`nav-tab ${activeTab === 'team' ? 'active' : ''}`}
            onClick={() => setActiveTab('team')}
          >
            My Team
          </button>
          <button 
            className={`nav-tab ${activeTab === 'league' ? 'active' : ''}`}
            onClick={() => setActiveTab('league')}
          >
            My League
          </button>
          <button 
            className={`nav-tab ${activeTab === 'agent' ? 'active' : ''}`}
            onClick={() => setActiveTab('agent')}
          >
            Agent Insights
          </button>
        </div>
      </header>

      <main className="animate-fade-in delay-100">
        {activeTab === 'team' && (
          <div className="glass-panel">
            <h2 style={{ marginBottom: '8px' }}>{teamName}</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>Manager: {managerName}</p>
            
            <h3 style={{ marginBottom: '16px' }}>Gameweek Performance</h3>
            <div className="grid-3">
              <div className="glass-panel" style={{ textAlign: 'center' }}>
                <h3 className="text-gradient" style={{ fontSize: '2rem' }}>{gwPoints}</h3>
                <p>GW Points</p>
              </div>
              <div className="glass-panel" style={{ textAlign: 'center' }}>
                <h3 className="text-gradient" style={{ fontSize: '2rem' }}>{overallPoints.toLocaleString()}</h3>
                <p>Overall Points</p>
              </div>
              <div className="glass-panel" style={{ textAlign: 'center' }}>
                <h3 className="text-gradient" style={{ fontSize: '2rem' }}>£{teamValue}m</h3>
                <p>Team Value</p>
              </div>
            </div>
            
            <h3 style={{ marginTop: '40px', marginBottom: '20px' }}>Top Performers</h3>
            <div className="grid-2">
              {topPerformers.map(p => (
                <div key={p.id} className="player-card">
                  <img src={`https://resources.premierleague.com/premierleague25/photos/players/110x140/${p.code}.png`} alt={p.web_name} className="player-img" />
                  <div className="player-info">
                    <h4>{p.web_name}</h4>
                    <p>{p.event_points * p.multiplier} pts {p.is_captain ? '(C)' : ''}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'league' && (
          <div className="glass-panel">
            <h2 style={{ marginBottom: '8px' }}>{userLeagueRaw?.league?.name || "League Standings"}</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>Top 10 Managers</p>
            
            {standings.slice(0, 10).map((team, index) => (
              <div key={team.id} className="glass-panel" style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', border: team.entry === userEntry.id ? '1px solid var(--accent-color)' : '' }}>
                <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                  <div>
                    <h4>{team.rank}. {team.entry_name}</h4>
                    <p style={{ color: 'var(--text-secondary)' }}>Manager: {team.player_name}</p>
                  </div>
                </div>
                <h3 className="text-gradient">{team.total.toLocaleString()}</h3>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'agent' && (
          <div className="glass-panel">
            <h2 style={{ marginBottom: '24px' }}>Agent Recommendations</h2>
            {agentData ? (
              <div className="grid-2">
                <div className="glass-panel">
                  <h3 style={{ color: 'var(--accent-color)', marginBottom: '16px' }}>Transfers In</h3>
                  <ul style={{ listStyle: 'none' }}>
                    {agentData.transfer_in?.map(p => (
                      <li key={p} style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.1rem' }}>
                         <span style={{ color: 'var(--accent-color)', fontWeight: 'bold' }}>+</span> {p}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="glass-panel">
                  <h3 style={{ color: 'var(--danger-color)', marginBottom: '16px' }}>Transfers Out</h3>
                  <p style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.1rem' }}>
                    <span style={{ color: 'var(--danger-color)', fontWeight: 'bold' }}>-</span> {agentData.transfer_out}
                  </p>
                </div>
                <div className="glass-panel" style={{ gridColumn: '1 / -1' }}>
                  <h3 style={{ marginBottom: '16px' }}>Reasoning</h3>
                  <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6', fontSize: '1.1rem' }}>{agentData.reasoning}</p>
                </div>
              </div>
            ) : (
              <p>Loading agent insights...</p>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

export default App
