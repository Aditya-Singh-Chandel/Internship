import React from 'react';
import { useAuth } from '../../context/AuthContext';

export default function PortalSidebar({ activeTab, onSelectTab }) {
  const { user } = useAuth();
  const rawRole = (typeof user?.role === 'object' ? user?.role?.name : user?.role) || '';
  const role = rawRole.toLowerCase();

  const menuItems = [
    {
      id: 'overview',
      label: 'Overview & Metrics',
      icon: '📊',
      roles: ['receptionist', 'manager', 'owner', 'admin']
    },
    {
      id: 'frontdesk',
      label: 'Front Desk & Stays',
      icon: '🛎️',
      roles: ['receptionist', 'manager', 'owner', 'admin']
    },
    {
      id: 'rooms',
      label: 'Physical Room Matrix',
      icon: '🛏️',
      roles: ['receptionist', 'manager', 'owner', 'admin']
    },
    {
      id: 'roomtypes',
      label: 'Room Types & Rates',
      icon: '🏷️',
      roles: ['manager', 'owner', 'admin']
    },
    {
      id: 'policies',
      label: 'Operational Policies',
      icon: '📜',
      roles: ['manager', 'owner', 'admin']
    },
    {
      id: 'knowledge',
      label: 'AI Knowledge & Docs',
      icon: '🧠',
      roles: ['manager', 'owner', 'admin']
    },
    {
      id: 'media',
      label: 'Photo Gallery & Media',
      icon: '🖼️',
      roles: ['manager', 'owner', 'admin']
    },
    {
      id: 'staff',
      label: 'Staff & Team Access',
      icon: '👥',
      roles: ['manager', 'owner', 'admin']
    },
    {
      id: 'hotels',
      label: 'Hotel Properties',
      icon: '🏢',
      roles: ['owner', 'admin']
    }
  ];

  const allowedItems = menuItems.filter(item => item.roles.includes(role));

  return (
    <aside className="portal-sidebar">
      <div className="portal-sidebar-title">
        Management Navigation
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {allowedItems.map(item => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectTab(item.id)}
              className={`portal-nav-btn ${isActive ? 'active' : ''}`}
            >
              <span className="icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Role Scoping Note */}
      <div className="portal-sidebar-footer">
        <strong>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#34d399', display: 'inline-block' }} />
          Security Clearance
        </strong>
        <span>
          Access scoped to <span style={{ color: '#dfc471', fontWeight: 600 }}>{role.toUpperCase()}</span> operations in PostgreSQL.
        </span>
      </div>
    </aside>
  );
}
