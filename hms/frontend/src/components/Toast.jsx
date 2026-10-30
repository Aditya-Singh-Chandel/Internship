import React from 'react';

export default function Toast({ toasts, onRemove }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className="toast-item">
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  );
}
