import { useState } from 'react'

const s = {
  hamburger: (open) => ({
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '6px',
    display: 'flex',
    flexDirection: 'column',
    gap: '5px',
    flexShrink: 0,
  }),
  bar: (open, i) => ({
    display: 'block',
    width: '22px',
    height: '2px',
    background: '#e2e8f0',
    borderRadius: '2px',
    transition: 'all 0.2s',
    transformOrigin: 'center',
    transform: open
      ? i === 0 ? 'translateY(7px) rotate(45deg)'
      : i === 1 ? 'scaleX(0)'
      : 'translateY(-7px) rotate(-45deg)'
      : 'none',
  }),
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.6)',
    zIndex: 100,
  },
  drawer: (open) => ({
    position: 'fixed',
    top: 0, left: 0, bottom: 0,
    width: '240px',
    background: '#1a1f2e',
    borderRight: '1px solid #2d3748',
    zIndex: 101,
    display: 'flex',
    flexDirection: 'column',
    transform: open ? 'translateX(0)' : 'translateX(-100%)',
    transition: 'transform 0.25s ease',
    boxShadow: open ? '4px 0 24px rgba(0,0,0,0.4)' : 'none',
  }),
  drawerHeader: {
    padding: '18px 20px 14px',
    borderBottom: '1px solid #2d3748',
    fontSize: '13px',
    color: '#4a5568',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  tab: (active) => ({
    display: 'flex',
    alignItems: 'center',
    padding: '13px 20px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: active ? 600 : 400,
    color: active ? '#e2e8f0' : '#718096',
    background: active ? 'rgba(99,179,237,0.1)' : 'none',
    borderLeft: `3px solid ${active ? '#63b3ed' : 'transparent'}`,
    border: 'none',
    borderLeftStyle: 'solid',
    borderLeftWidth: '3px',
    borderLeftColor: active ? '#63b3ed' : 'transparent',
    width: '100%',
    textAlign: 'left',
    transition: 'all 0.15s',
  }),
}

export default function TabNav({ tabs, activeTab, onTabChange, open, onToggle }) {
  const select = (id) => {
    onTabChange(id)
    onToggle(false)
  }

  return (
    <>
      {/* Hamburger trigger — rendered here, positioned in header by parent */}
      <button style={s.hamburger(open)} onClick={() => onToggle(!open)} aria-label="Menu">
        {[0, 1, 2].map(i => <span key={i} style={s.bar(open, i)} />)}
      </button>

      {/* Overlay */}
      {open && <div style={s.overlay} onClick={() => onToggle(false)} />}

      {/* Slide-in drawer */}
      <div style={s.drawer(open)}>
        <div style={s.drawerHeader}>Navigation</div>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            style={s.tab(activeTab === tab.id)}
            onClick={() => select(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </>
  )
}
