import React, { useState, useEffect, useRef } from "react";
import { api } from "../../services/api";

export default function PortalKnowledge({
  activeHotel,
  token,
  userRole
}) {
  const [documents, setDocuments] = useState([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Upload Form State
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadCategory, setUploadCategory] = useState("policy");
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef(null);

  const canManage = ["admin", "owner", "manager"].includes(userRole);

  const fetchDocs = async () => {
    if (!activeHotel?.id) return;
    setIsLoadingDocs(true);
    try {
      const docs = await api.getHotelDocuments(activeHotel.id, token);
      setDocuments(docs || []);
    } catch (err) {
      console.error("Failed to load documents", err);
    } finally {
      setIsLoadingDocs(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, [activeHotel?.id]);

  const handleSyncKnowledge = async () => {
    if (!activeHotel?.id) return;
    setIsSyncing(true);
    setError(null);
    setSuccess(null);

    try {
      const res = await api.syncHotelDatabaseKnowledge(activeHotel.id, token);
      const chunksCount = res?.data?.chunks_created ?? res?.chunks_created ?? "multiple";
      setSuccess(
        `Knowledge Synchronized! Vectorized database policies, suite specs, and amenities into ${chunksCount} semantic chunks for ${activeHotel.name}.`
      );
      fetchDocs();
    } catch (err) {
      setError(err.message || "Failed to synchronize hotel knowledge base.");
    } finally {
      setIsSyncing(false);
    }
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setError("Please choose a PDF, TXT, or DOCX document to upload.");
      return;
    }
    if (!activeHotel?.id) return;

    setIsUploading(true);
    setError(null);
    setSuccess(null);

    try {
      await api.uploadHotelDocument(
        activeHotel.id,
        selectedFile,
        uploadTitle || selectedFile.name,
        uploadCategory,
        token
      );
      setSuccess(`Document "${uploadTitle || selectedFile.name}" uploaded and queued for vectorization!`);
      setSelectedFile(null);
      setUploadTitle("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      fetchDocs();
    } catch (err) {
      setError(err.message || "Failed to upload document.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteDocument = async (doc) => {
    if (!window.confirm(`Delete document "${doc.title || doc.filename}" from AI knowledge base?`)) {
      return;
    }

    try {
      await api.deleteHotelDocument(activeHotel.id, doc.id, token);
      setSuccess(`Deleted document "${doc.title || doc.filename}".`);
      fetchDocs();
    } catch (err) {
      setError(err.message || "Failed to delete document.");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Top Banner */}
      <div className="portal-banner">
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: "rgba(168, 85, 247, 0.15)",
              border: "1px solid rgba(168, 85, 247, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 22
            }}
          >
            🧠
          </div>
          <div>
            <h1 className="portal-banner-title">AI Concierge Knowledge Base (RAG)</h1>
            <p className="portal-banner-subtitle">
              FastEmbed vector semantic search engine & document repository for{" "}
              <span style={{ color: "#dfc471", fontWeight: 600 }}>{activeHotel?.name}</span>
            </p>
          </div>
        </div>

        {canManage && (
          <button
            onClick={handleSyncKnowledge}
            disabled={isSyncing}
            className="portal-btn-gold"
          >
            {isSyncing ? (
              <span>⚡ Vectorizing Knowledge...</span>
            ) : (
              <>
                <span>⚡</span>
                <span>Synchronize Database to AI</span>
              </>
            )}
          </button>
        )}
      </div>

      {/* Notifications */}
      {error && (
        <div className="portal-alert-error">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <strong>⚠️ Error:</strong>
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            style={{ background: "none", border: "none", color: "#fca5a5", cursor: "pointer", fontSize: 16 }}
          >
            ✕
          </button>
        </div>
      )}
      {success && (
        <div className="portal-alert-success">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <strong>✓ Success:</strong>
            <span>{success}</span>
          </div>
          <button
            onClick={() => setSuccess(null)}
            style={{ background: "none", border: "none", color: "#6ee7b7", cursor: "pointer", fontSize: 16 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* RAG Engine Info Cards */}
      <div className="portal-grid-3">
        <div className="portal-card">
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
            <span style={{ fontSize: 28 }}>🤖</span>
            <div>
              <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase" }}>
                Embedding Model
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#ffffff", fontFamily: "monospace" }}>
                BAAI/bge-small-en-v1.5
              </div>
            </div>
          </div>
          <p style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.5, margin: 0 }}>
            FastEmbed 384-dimensional dense semantic vectors with cosine similarity scoring.
          </p>
        </div>

        <div className="portal-card">
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
            <span style={{ fontSize: 28 }}>⚡</span>
            <div>
              <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase" }}>
                Knowledge Scope
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#dfc471" }}>
                Database + Documents
              </div>
            </div>
          </div>
          <p style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.5, margin: 0 }}>
            Real-time synchronization aggregates hotel cancellation policies, suite rates, and custom uploaded manuals.
          </p>
        </div>

        <div className="portal-card">
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
            <span style={{ fontSize: 28 }}>📚</span>
            <div>
              <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase" }}>
                Active Knowledge Docs
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#c084fc" }}>
                {documents.length} Uploaded Files
              </div>
            </div>
          </div>
          <p style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.5, margin: 0 }}>
            Documents parsed into searchable chunks linked directly to live guest AI concierge chats.
          </p>
        </div>
      </div>

      {/* Document Upload Section */}
      {canManage && (
        <div className="portal-card">
          <div className="portal-card-header">
            <div>
              <h2 className="portal-card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span>📄</span>
                <span>Upload Hotel Knowledge Document</span>
              </h2>
              <p className="portal-card-subtitle">
                Add seasonal spa brochures, dining menus, wedding packages, or operational rulebooks to the AI brain.
              </p>
            </div>
          </div>

          <form onSubmit={handleFileUpload} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="portal-form-row-3">
              <div className="portal-form-group">
                <label className="portal-label">Document Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Winter 2026 Spa & Wellness Guide"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  className="portal-input"
                />
              </div>

              <div className="portal-form-group">
                <label className="portal-label">Category</label>
                <select
                  value={uploadCategory}
                  onChange={(e) => setUploadCategory(e.target.value)}
                  className="portal-select"
                >
                  <option value="policy">Operational Policy</option>
                  <option value="dining_menu">Dining & Wine Menus</option>
                  <option value="spa_wellness">Spa & Wellness</option>
                  <option value="local_guide">Concierge Local Guide</option>
                  <option value="general">General Operations</option>
                </select>
              </div>

              <div className="portal-form-group">
                <label className="portal-label">File Attachment (PDF, TXT, DOCX) *</label>
                <input
                  type="file"
                  ref={fileInputRef}
                  required
                  accept=".pdf,.txt,.docx"
                  onChange={(e) => setSelectedFile(e.target.files[0] || null)}
                  className="portal-input"
                  style={{ padding: "8px 12px" }}
                />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button type="submit" disabled={isUploading} className="portal-btn-gold">
                {isUploading ? "Uploading & Vectorizing..." : "⬆️ Upload & Parse Document"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Document Library Table */}
      <div className="portal-card" style={{ padding: 0, overflow: "hidden" }}>
        <div
          style={{
            padding: "20px 24px",
            borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}
        >
          <div>
            <h2 className="portal-card-title">Document Repository</h2>
            <p className="portal-card-subtitle">
              Files currently parsed into knowledge vectors for {activeHotel?.name}
            </p>
          </div>
          <button
            onClick={fetchDocs}
            disabled={isLoadingDocs}
            className="portal-btn-secondary"
          >
            <span>🔄</span>
            <span>Refresh</span>
          </button>
        </div>

        <div className="portal-table-wrap" style={{ border: "none", borderRadius: 0 }}>
          <table className="portal-table">
            <thead>
              <tr>
                <th>Document Title</th>
                <th>Category</th>
                <th>Format</th>
                <th>Chunks Vectorized</th>
                <th>Uploaded Date</th>
                {canManage && <th style={{ textAlign: "right" }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {isLoadingDocs ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: 48, color: "#94a3b8" }}>
                    Loading knowledge documents...
                  </td>
                </tr>
              ) : documents.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: 48, color: "#94a3b8" }}>
                    <div style={{ fontSize: 32, marginBottom: 8 }}>📂</div>
                    <div style={{ fontWeight: 600, color: "#e2e8f0" }}>No custom documents uploaded yet for this property.</div>
                    <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
                      Click "Synchronize Database to AI" above to vectorize database policies and room specs!
                    </div>
                  </td>
                </tr>
              ) : (
                documents.map((doc) => (
                  <tr key={doc.id}>
                    <td style={{ fontWeight: 600, color: "#ffffff" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span>📄</span>
                        <span>{doc.title || doc.filename || "Untitled Document"}</span>
                      </div>
                    </td>
                    <td>
                      <span className="portal-badge portal-badge-gray">
                        {doc.category || "General"}
                      </span>
                    </td>
                    <td style={{ fontFamily: "monospace", textTransform: "uppercase", color: "#94a3b8" }}>
                      {doc.file_type || doc.filename?.split(".").pop() || "PDF"}
                    </td>
                    <td style={{ fontFamily: "monospace", color: "#dfc471", fontWeight: 600 }}>
                      {doc.chunk_count || doc.chunks?.length || "Auto"} chunks
                    </td>
                    <td style={{ color: "#94a3b8" }}>
                      {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : "Active"}
                    </td>
                    {canManage && (
                      <td style={{ textAlign: "right" }}>
                        <button
                          onClick={() => handleDeleteDocument(doc)}
                          className="portal-btn-danger"
                        >
                          Remove
                        </button>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
