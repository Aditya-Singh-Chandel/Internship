import React, { useState, useRef, useEffect } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

function FormattedMessage({ content, isUser }) {
  if (!content) return null;

  // Helper to parse bold, italic, code inline without exposing raw asterisks
  const renderInline = (str) => {
    if (!str) return null;

    // Clean any accidental triple or quadruple asterisks
    const cleanStr = str.replace(/\*{3,}/g, '');

    const tokens = [];
    const regex = /(\*\*.*?\*\*|\*.*?\*|`.*?`)/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(cleanStr)) !== null) {
      if (match.index > lastIndex) {
        tokens.push(cleanStr.substring(lastIndex, match.index));
      }

      const raw = match[0];
      if (raw.startsWith('**') && raw.endsWith('**') && raw.length > 4) {
        tokens.push(
          <strong 
            key={match.index} 
            style={{ 
              fontWeight: 700, 
              color: isUser ? '#ffffff' : 'var(--navy-900, #0f172a)' 
            }}
          >
            {raw.slice(2, -2)}
          </strong>
        );
      } else if (raw.startsWith('*') && raw.endsWith('*') && raw.length > 2) {
        tokens.push(
          <em key={match.index} style={{ fontStyle: 'italic', opacity: isUser ? 0.95 : 0.85 }}>
            {raw.slice(1, -1)}
          </em>
        );
      } else if (raw.startsWith('`') && raw.endsWith('`') && raw.length > 2) {
        tokens.push(
          <code 
            key={match.index} 
            style={{ 
              background: isUser ? 'rgba(255,255,255,0.15)' : '#f1f5f9', 
              padding: '1px 5px', 
              borderRadius: '4px', 
              fontSize: '11px',
              fontFamily: 'monospace' 
            }}
          >
            {raw.slice(1, -1)}
          </code>
        );
      }
      lastIndex = regex.lastIndex;
    }

    if (lastIndex < cleanStr.length) {
      tokens.push(cleanStr.substring(lastIndex));
    }

    return tokens.length > 0 ? tokens : cleanStr;
  };

  const lines = content.split('\n');
  const elements = [];
  let currentList = null;
  let listType = null; // 'ul' | 'ol'

  const flushList = () => {
    if (currentList && currentList.length > 0) {
      const isOrdered = listType === 'ol';
      const ListTag = isOrdered ? 'ol' : 'ul';
      elements.push(
        <ListTag 
          key={`list-${elements.length}`} 
          style={{ 
            paddingLeft: isOrdered ? '22px' : '18px', 
            margin: '6px 0 10px', 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '6px' 
          }}
        >
          {currentList.map((item, i) => (
            <li key={i} style={{ fontSize: '12.5px', lineHeight: '1.55' }}>
              {renderInline(item)}
            </li>
          ))}
        </ListTag>
      );
      currentList = null;
      listType = null;
    }
  };

  lines.forEach((rawLine, idx) => {
    const line = rawLine.trim();

    if (!line) {
      flushList();
      return;
    }

    // Horizontal Rule
    if (line === '---' || line === '***') {
      flushList();
      elements.push(
        <hr key={idx} style={{ border: 'none', borderTop: '1px solid #e2e8f0', margin: '10px 0' }} />
      );
      return;
    }

    // Headers
    if (line.startsWith('### ')) {
      flushList();
      elements.push(
        <div 
          key={idx} 
          style={{ 
            fontWeight: 700, 
            fontSize: '13.5px', 
            color: isUser ? '#ffffff' : 'var(--navy-900, #0f172a)', 
            margin: '10px 0 4px',
            letterSpacing: '0.02em'
          }}
        >
          {renderInline(line.slice(4))}
        </div>
      );
      return;
    }

    if (line.startsWith('## ') || line.startsWith('# ')) {
      flushList();
      elements.push(
        <div 
          key={idx} 
          style={{ 
            fontWeight: 750, 
            fontSize: '14px', 
            color: isUser ? '#ffffff' : 'var(--navy-900, #0f172a)', 
            margin: '12px 0 6px',
            borderBottom: isUser ? 'none' : '1px solid #e2e8f0',
            paddingBottom: '3px'
          }}
        >
          {renderInline(line.replace(/^#+\s*/, ''))}
        </div>
      );
      return;
    }

    // Numbered List: e.g. "1. " or "1) "
    const numMatch = line.match(/^(\d+)[\.\)]\s+(.*)$/);
    if (numMatch) {
      if (listType !== 'ol') {
        flushList();
        listType = 'ol';
        currentList = [];
      }
      currentList.push(numMatch[2]);
      return;
    }

    // Bullet List: e.g. "* ", "- ", "• "
    const bulletMatch = line.match(/^[\*\-•]\s+(.*)$/);
    if (bulletMatch) {
      if (listType !== 'ul') {
        flushList();
        listType = 'ul';
        currentList = [];
      }
      currentList.push(bulletMatch[1]);
      return;
    }

    // Regular text paragraph
    flushList();
    elements.push(
      <p 
        key={idx} 
        style={{ 
          margin: '0 0 8px', 
          fontSize: '12.5px', 
          lineHeight: '1.55',
          color: isUser ? '#ffffff' : '#1e293b' 
        }}
      >
        {renderInline(line)}
      </p>
    );
  });

  flushList();

  return <div className="concierge-message-body">{elements}</div>;
}

export default function AIConcierge({ 
  isOpen, 
  onClose, 
  onToggle, 
  hotels = [], 
  scopedHotel = null 
}) {
  const { user, token } = useAuth();
  const [selectedHotelId, setSelectedHotelId] = useState(scopedHotel?.id || "");
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Welcome to GrandStay Hotels & Resorts. I am your personal AI Concierge. How may I assist your travel plans today? You can ask me about our luxury properties, room suites, dining hours, pool cabanas, guest reviews, or cancellation policies.',
      citations: []
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  const handleResetChat = () => {
    setSessionId(null);
    setInput('');
    const welcomeMsg = user ? {
      role: 'assistant',
      content: `Welcome to GrandStay Hotels & Resorts, ${user.name}! I am your personal AI Concierge. How may I assist your travel plans today? You can ask me about your reservations, suite recommendations, resort amenities, or dining experiences.`,
      citations: []
    } : {
      role: 'assistant',
      content: 'Welcome to GrandStay Hotels & Resorts. I am your personal AI Concierge. How may I assist your travel plans today? You can ask me about our luxury properties, room suites, dining hours, pool cabanas, guest reviews, or cancellation policies.',
      citations: []
    };
    setMessages([welcomeMsg]);
  };

  // Automatically refresh chat whenever authentication state changes (login or logout)
  useEffect(() => {
    handleResetChat();
  }, [user?.id]);

  useEffect(() => {
    if (scopedHotel?.id) {
      setSelectedHotelId(scopedHotel.id);
    }
  }, [scopedHotel]);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  // Dynamically generate prompt chips based on scoped hotel or actual hotel portfolio
  const promptChips = scopedHotel ? [
    `What are the dining hours at ${scopedHotel.name}?`,
    `What is the cancellation policy for ${scopedHotel.name}?`,
    `Tell me about the suites and amenities at ${scopedHotel.name}`,
    `What do guest reviews say about ${scopedHotel.name}?`
  ] : [
    `What is the cancellation policy at ${hotels[0]?.name || "Alpine Peak Lodge"}?`,
    `Which ${hotels[0]?.city || "Miami"} hotel has the best verified guest reviews?`,
    `What suites are available at ${hotels[1]?.name || hotels[0]?.name || "Grand Mirage"}?`,
    `How does the refund calculation work for reservations?`
  ];


  const handleSend = async (textToSend = null) => {
    const query = (textToSend || input).trim();
    if (!query || loading) return;

    const userMsg = { role: 'user', content: query };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const activeToken = token || (typeof window !== "undefined" && window.localStorage ? localStorage.getItem("grandstay_customer_token") : null);
      const resp = await api.sendChatMessage(
        query, 
        selectedHotelId || null, 
        sessionId || null, 
        activeToken
      );

      if (resp?.session_id) {
        setSessionId(resp.session_id);
      }

      const assistantMsg = {
        role: 'assistant',
        content: resp.response,
        citations: resp.citations || []
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg = {
        role: 'assistant',
        content: `I apologize, but I encountered an issue contacting the concierge service: ${err.message || 'Please try again momentarily.'}`,
        citations: []
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating Launcher Button */}
      <div className="concierge-launcher" onClick={onToggle}>
        <div className="concierge-icon-orb">⚜</div>
        <span>AI Concierge</span>
      </div>

      {/* Concierge Drawer Panel */}
      {isOpen && (
        <div className="concierge-drawer" data-lenis-prevent>
          {/* Header */}
          <div className="concierge-drawer-head">
            <div className="concierge-head-brand">
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, var(--gold-400), var(--gold-600))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '16px'
              }}>
                ⚜
              </div>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.04em' }}>GrandStay AI Concierge</div>
                <div style={{ fontSize: '10px', color: 'var(--gold-400)' }}>Grounded in Verified Hotel Records</div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                type="button"
                title="Start a fresh conversation"
                style={{
                  background: 'rgba(255, 255, 255, 0.1)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  borderRadius: '6px',
                  color: '#e2e8f0',
                  fontSize: '11px',
                  padding: '4px 8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'background 0.2s'
                }}
                onClick={handleResetChat}
              >
                <span>↺</span> New Chat
              </button>
              <button
                type="button"
                style={{ color: 'rgba(255,255,255,0.7)', fontSize: '18px', cursor: 'pointer', background: 'none', border: 'none' }}
                onClick={onClose}
              >
                ✕
              </button>
            </div>
          </div>

          {/* Hotel Scope Selector Bar */}
          <div style={{
            padding: '8px 14px',
            background: '#f8fafc',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flexShrink: 0
          }}>
            <span style={{ fontSize: '11px', color: '#64748b', fontWeight: 600 }}>Scope:</span>
            <select
              style={{
                flex: 1,
                fontSize: '11px',
                padding: '4px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid #cbd5e1',
                background: '#ffffff',
                outline: 'none',
                color: 'var(--navy-900)'
              }}
              value={selectedHotelId}
              onChange={(e) => setSelectedHotelId(e.target.value)}
            >
              <option value="">All Luxury Properties</option>
              {hotels.map(h => (
                <option key={h.id} value={h.id}>🏨 {h.name}</option>
              ))}
            </select>
          </div>

          {/* Messages Feed */}
          <div className="concierge-drawer-messages" data-lenis-prevent>
            {messages.map((m, idx) => (
              <div key={idx} className={`chat-bubble ${m.role}`}>
                <FormattedMessage content={m.content} isUser={m.role === 'user'} />

                {/* Verified Citations List */}
                {m.citations && m.citations.length > 0 && (
                  <div style={{
                    marginTop: '10px',
                    paddingTop: '8px',
                    borderTop: '1px solid rgba(0,0,0,0.08)',
                    fontSize: '11px',
                    color: '#64748b'
                  }}>
                    <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--gold-700)' }}>
                      Verified Evidence Citations:
                    </strong>
                    {m.citations.slice(0, 3).map((c, cIdx) => (
                      <div key={cIdx} style={{ marginBottom: '2px' }}>
                        • <em>[{c.source_type}]</em> {c.title}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="chat-bubble assistant" style={{ fontStyle: 'italic', color: '#64748b' }}>
                Consulting hotel knowledge and policies...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggestion Chips */}
          <div 
            className="concierge-chips-bar"
            style={{
              padding: '8px 12px',
              background: 'var(--cream-100)',
              borderTop: '1px solid #f1f5f9',
              display: 'flex',
              gap: '6px',
              overflowX: 'auto',
              whiteSpace: 'nowrap',
              flexShrink: 0
            }}
          >
            {promptChips.map((chip, idx) => (
              <button
                key={idx}
                type="button"
                style={{
                  fontSize: '10px',
                  fontWeight: 600,
                  padding: '4px 10px',
                  borderRadius: 'var(--radius-full)',
                  background: '#ffffff',
                  border: '1px solid #cbd5e1',
                  color: 'var(--navy-900)',
                  cursor: 'pointer',
                  flexShrink: 0
                }}
                onClick={() => handleSend(chip)}
              >
                {chip}
              </button>
            ))}
          </div>

          {/* Input Bar */}
          <form 
            className="concierge-drawer-input-bar"
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
          >
            <input
              type="text"
              placeholder="Ask about hotels, suites, breakfast, policies..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--surface-border)',
                fontSize: '0.86rem',
                outline: 'none'
              }}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="btn-primary"
              style={{ padding: '8px 16px', fontSize: '0.86rem', opacity: (loading || !input.trim()) ? 0.6 : 1 }}
            >
              Send
            </button>
          </form>
        </div>
      )}
    </>
  );
}
