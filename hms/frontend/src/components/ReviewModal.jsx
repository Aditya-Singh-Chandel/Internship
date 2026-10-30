import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function ReviewModal({ 
  isOpen, 
  onClose, 
  booking, 
  hotel, 
  existingReview = null,
  onReviewSubmitted 
}) {
  const { token } = useAuth();
  const [rating, setRating] = useState(5);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (existingReview) {
      setRating(existingReview.rating || 5);
      setComment(existingReview.comment || '');
    } else {
      setRating(5);
      setComment('');
    }
    setError('');
  }, [existingReview, isOpen]);

  if (!isOpen || !booking) return null;

  const isEditing = Boolean(existingReview && existingReview.id);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!comment.trim()) {
      setError("Please provide a short comment describing your stay experience.");
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      if (isEditing) {
        await api.updateReview(existingReview.id, {
          rating,
          comment: comment.trim()
        }, token);
      } else {
        await api.submitReview({
          booking_id: booking.id,
          rating,
          comment: comment.trim()
        }, token);
      }

      onReviewSubmitted?.();
      onClose();
    } catch (err) {
      setError(err.message || "Failed to save review. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("Are you sure you want to delete this verified review?")) return;
    setDeleting(true);
    setError('');
    try {
      await api.deleteReview(existingReview.id, token);
      onReviewSubmitted?.();
      onClose();
    } catch (err) {
      setError(err.message || "Failed to delete review.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="modal-overlay" data-lenis-prevent onClick={onClose}>
      <div className="modal-card" data-lenis-prevent style={{ maxWidth: '480px' }} onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close-btn" onClick={onClose}>✕</button>

        <div style={{ padding: '32px' }}>
          <div style={{ textAlign: 'center', marginBottom: '22px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--gold-600)' }}>
              {isEditing ? "Verified Guest Review • Edit Mode" : "Verified Guest Review"}
            </span>
            <h2 style={{ fontSize: '1.6rem', color: 'var(--navy-950)', marginTop: '2px' }}>
              {isEditing ? "Edit Your Feedback" : "How was your stay?"}
            </h2>
            <p style={{ fontSize: '0.88rem' }}>
              {isEditing 
                ? `Update your published rating and comments for ${hotel?.name || "your hotel stay"}.`
                : `Share your feedback for ${hotel?.name || "your hotel stay"}. Your review helps future guests and guides our concierge.`}
            </p>
          </div>

          {error && (
            <div style={{
              background: 'var(--error-bg)',
              color: 'var(--error)',
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.84rem',
              marginBottom: '16px',
              border: '1px solid #fecaca'
            }}>
              ⚠️ {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            {/* Interactive Star Rating */}
            <div style={{ textAlign: 'center' }}>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Your Star Rating
              </label>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', fontSize: '32px', cursor: 'pointer' }}>
                {[1, 2, 3, 4, 5].map((star) => (
                  <span
                    key={star}
                    style={{
                      color: (hoverRating || rating) >= star ? '#eab308' : '#cbd5e1',
                      transition: 'color var(--transition-fast)'
                    }}
                    onMouseEnter={() => setHoverRating(star)}
                    onMouseLeave={() => setHoverRating(0)}
                    onClick={() => setRating(star)}
                  >
                    ★
                  </span>
                ))}
              </div>
              <span style={{ fontSize: '0.82rem', color: 'var(--gold-700)', fontWeight: 600 }}>
                {rating === 5 ? "Exceptional (5/5)" : rating === 4 ? "Very Good (4/5)" : rating === 3 ? "Average (3/5)" : "Could Be Improved"}
              </span>
            </div>

            {/* Comment */}
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                Detailed Feedback *
              </label>
              <textarea
                rows={4}
                required
                placeholder="What did you love about the suite, breakfast, views, spa, or concierge service?"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--surface-border)',
                  fontSize: '0.9rem',
                  outline: 'none',
                  resize: 'none'
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              {isEditing && (
                <button
                  type="button"
                  disabled={submitting || deleting}
                  onClick={handleDelete}
                  className="btn-secondary"
                  style={{
                    padding: '12px 16px',
                    fontSize: '0.88rem',
                    color: '#dc2626',
                    borderColor: '#fca5a5'
                  }}
                >
                  {deleting ? "Deleting..." : "🗑️ Delete"}
                </button>
              )}
              <button
                type="submit"
                disabled={submitting || deleting}
                className="btn-primary"
                style={{
                  flex: 1,
                  padding: '12px',
                  fontSize: '0.95rem',
                  opacity: submitting ? 0.7 : 1
                }}
              >
                {submitting 
                  ? (isEditing ? "Updating Review..." : "Publishing Review...") 
                  : (isEditing ? "Update Verified Review" : "Submit Verified Review")}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
