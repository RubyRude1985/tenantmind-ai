"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Auth = { access_token: string; user_name: string; workspace_name: string };
type DocumentItem = { id: string; title: string; filename: string | null; mime_type: string; status: string; chunk_count: number; created_at: string };
type Citation = { document_id: string; title: string; excerpt: string; page_number: number | null; similarity: number };
type ChatResult = { answer: string; citations: Citation[]; mode: string };
type Stats = { documents: number; chunks: number; questions: number; latest_activity: { action: string; details: string; created_at: string }[] };

const API = process.env.NEXT_PUBLIC_API_URL ?? "/backend";

export default function Home() {
  const [auth, setAuth] = useState<Auth | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [stats, setStats] = useState<Stats>({ documents: 0, chunks: 0, questions: 0, latest_activity: [] });
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<ChatResult | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const request = useCallback(async (path: string, options: RequestInit = {}) => {
    if (!auth) throw new Error("Sign in required");
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: { Authorization: `Bearer ${auth.access_token}`, ...(options.headers ?? {}) },
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail ?? "Request failed");
    }
    return response;
  }, [auth]);

  const refresh = useCallback(async () => {
    if (!auth) return;
    const [docsResponse, statsResponse] = await Promise.all([request("/api/documents"), request("/api/dashboard")]);
    setDocuments(await docsResponse.json());
    setStats(await statsResponse.json());
  }, [auth, request]);

  useEffect(() => { refresh().catch((err) => setError(err.message)); }, [refresh]);
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("demo") === "1") enterDemo();
  }, []);

  async function enterDemo() {
    setBusy("auth"); setError("");
    try {
      const response = await fetch(`${API}/api/auth/demo`, { method: "POST" });
      if (!response.ok) throw new Error("Demo workspace could not be created");
      setAuth(await response.json());
    } catch (err) { setError(err instanceof Error ? err.message : "Unexpected error"); }
    finally { setBusy(""); }
  }

  async function addSamples() {
    setBusy("sample"); setError("");
    const samples = [
      { title: "Customer Refund Policy", content: "Refund requests are reviewed within five business days. Approved refunds return to the original payment method within three to seven business days. Requests older than 30 days require finance manager approval." },
      { title: "Security & Access Handbook", content: "All team members must use multi-factor authentication. Production access requires manager approval, expires after eight hours, and is recorded in the audit log. Credentials must never be shared through email or chat." },
    ];
    try {
      for (const sample of samples) await request("/api/documents/text", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sample) });
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Unexpected error"); }
    finally { setBusy(""); }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy("upload"); setError("");
    const form = event.currentTarget;
    const input = form.elements.namedItem("file") as HTMLInputElement;
    if (!input.files?.[0]) { setError("Choose a PDF, TXT, or Markdown file."); setBusy(""); return; }
    const data = new FormData(); data.append("file", input.files[0]);
    try { await request("/api/documents/upload", { method: "POST", body: data }); form.reset(); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Unexpected error"); }
    finally { setBusy(""); }
  }

  async function ask(event: FormEvent) {
    event.preventDefault(); setBusy("chat"); setError(""); setResult(null);
    try {
      const response = await request("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
      setResult(await response.json()); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Unexpected error"); }
    finally { setBusy(""); }
  }

  async function removeDocument(id: string) {
    setBusy(id);
    try { await request(`/api/documents/${id}`, { method: "DELETE" }); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Unexpected error"); }
    finally { setBusy(""); }
  }

  if (!auth) return (
    <main className="landing">
      <nav><div className="brand"><span>T</span>TenantMind</div><span className="navPill">PORTFOLIO DEMO</span></nav>
      <section className="landingGrid">
        <div>
          <p className="eyebrow">SECURE KNOWLEDGE INFRASTRUCTURE</p>
          <h1>Answers your team<br /><em>can actually trust.</em></h1>
          <p className="lead">A multi-tenant RAG workspace that turns internal documents into cited, permission-aware answers.</p>
          <button className="cta" onClick={enterDemo} disabled={busy === "auth"}>{busy === "auth" ? "Preparing workspace…" : "Enter live demo →"}</button>
          {error && <div className="error">{error}</div>}
          <div className="techRow"><span>Next.js 16</span><span>FastAPI</span><span>PostgreSQL + pgvector</span><span>OpenAI</span></div>
        </div>
        <div className="architectureCard">
          <div className="archTop"><span>LIVE ARCHITECTURE</span><i>● HEALTHY</i></div>
          <div className="archNode accent">Next.js workspace</div><b>↓ JWT + REST</b>
          <div className="archNode">FastAPI tenant boundary</div><b>↓ chunk + embed</b>
          <div className="archSplit"><div>PostgreSQL<br /><small>metadata</small></div><div>pgvector<br /><small>semantic search</small></div></div>
          <div className="archFoot">Grounded generation · citations · audit trail</div>
        </div>
      </section>
    </main>
  );

  return (
    <main className="appShell">
      <aside>
        <div className="brand light"><span>T</span>TenantMind</div>
        <div className="workspaceLabel">WORKSPACE</div><div className="workspaceName">◈ {auth.workspace_name}</div>
        <div className="sideNav"><b>▦ Overview</b><span>◫ Knowledge</span><span>✦ Assistant</span><span>⌁ Audit log</span></div>
        <div className="userCard"><div>{auth.user_name.slice(0, 1)}</div><span><b>{auth.user_name}</b><small>Workspace admin</small></span></div>
      </aside>
      <section className="content">
        <header><div><p className="eyebrow">KNOWLEDGE OPERATIONS</p><h2>Workspace overview</h2></div><span className="status">● SYSTEM HEALTHY</span></header>
        {error && <div className="error">{error}</div>}
        <div className="stats">
          <div><span>DOCUMENTS</span><b>{stats.documents}</b><small>isolated sources</small></div>
          <div><span>VECTOR CHUNKS</span><b>{stats.chunks}</b><small>searchable passages</small></div>
          <div><span>QUESTIONS</span><b>{stats.questions}</b><small>audited queries</small></div>
          <div><span>SECURITY</span><b className="shield">JWT</b><small>tenant-scoped access</small></div>
        </div>
        <div className="mainGrid">
          <section className="panel assistantPanel">
            <div className="panelTitle"><div><p className="eyebrow">GROUNDED ASSISTANT</p><h3>Ask across your knowledge</h3></div><span>RAG</span></div>
            <form onSubmit={ask} className="askForm">
              <textarea aria-label="Question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What is required for production access?" required minLength={3} />
              <button disabled={busy === "chat"}>{busy === "chat" ? "Retrieving evidence…" : "Ask with evidence →"}</button>
            </form>
            {result ? <div className="answerBox">
              <div className="answerMeta">✦ {result.mode} · {result.citations.length} sources</div><p>{result.answer}</p>
              <div className="citations">{result.citations.map((c, i) => <article key={`${c.document_id}-${i}`}>
                <div><b>[{i + 1}] {c.title}</b><span>{Math.round(c.similarity * 100)}% match{c.page_number ? ` · page ${c.page_number}` : ""}</span></div><p>{c.excerpt}</p>
              </article>)}</div>
            </div> : <div className="answerEmpty"><b>✦</b><span>Answers are generated only from retrieved workspace evidence.</span></div>}
          </section>
          <section className="panel ingestionPanel">
            <div className="panelTitle"><div><p className="eyebrow">INGESTION PIPELINE</p><h3>Add knowledge</h3></div></div>
            <form onSubmit={upload} className="uploadBox"><input name="file" type="file" accept=".pdf,.txt,.md" /><div><b>Drop in a source document</b><span>PDF, TXT or Markdown · max 8 MB</span></div><button disabled={busy === "upload"}>{busy === "upload" ? "Chunking & embedding…" : "Process document"}</button></form>
            <div className="pipeline"><span>01 Extract</span><i>→</i><span>02 Chunk</span><i>→</i><span>03 Embed</span><i>→</i><span>04 Index</span></div>
            {documents.length === 0 && <button className="sampleButton" onClick={addSamples} disabled={busy === "sample"}>{busy === "sample" ? "Indexing samples…" : "+ Load sample knowledge"}</button>}
            <div className="docList">{documents.map(doc => <article key={doc.id}><div className="fileIcon">{doc.filename?.endsWith(".pdf") ? "PDF" : "TXT"}</div><div><b>{doc.title}</b><span>{doc.chunk_count} chunks · {doc.status}</span></div><button aria-label={`Delete ${doc.title}`} onClick={() => removeDocument(doc.id)} disabled={busy === doc.id}>×</button></article>)}</div>
          </section>
        </div>
        <section className="panel activityPanel"><div className="panelTitle"><div><p className="eyebrow">AUDITABILITY</p><h3>Recent activity</h3></div><span>Last 5 events</span></div>
          <div className="activityList">{stats.latest_activity.length === 0 ? <p>No activity yet.</p> : stats.latest_activity.map((item, index) => <div key={`${item.created_at}-${index}`}><i>{item.action === "question.asked" ? "?" : "✓"}</i><b>{item.action.replace(".", " ")}</b><span>{item.details}</span><time>{new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div>)}</div>
        </section>
      </section>
    </main>
  );
}
