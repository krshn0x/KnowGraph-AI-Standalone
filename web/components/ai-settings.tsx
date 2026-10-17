"use client";

import { useState } from "react";
import { KeyRound, Save, ShieldCheck, Unplug, Network } from "lucide-react";
import { api } from "@/lib/api";
import type { AIConnectionTest, AISettings, Provider } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { ErrorNotice, Loading, Modal } from "./ui";

export function AISettingsModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const settings = useResource<AISettings>("/settings/ai");
  return <Modal title="AI settings" onClose={onClose}>
    {settings.loading ? <Loading label="Loading provider settings…" /> : settings.error ? <ErrorNotice message={settings.error} /> : settings.data && <AISettingsForm initial={settings.data} onSaved={onSaved} />}
  </Modal>;
}

function AISettingsForm({ initial, onSaved }: { initial: AISettings; onSaved: () => void }) {
  const [provider, setProvider] = useState<Provider>(initial.provider);
  const [values, setValues] = useState(initial.providers);
  const [key, setKey] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<AIConnectionTest | null>(null);
  const current = values[provider];
  const update = (field: "model" | "base_url", value: string) => { setTestResult(null); setError(""); setValues(all => ({ ...all, [provider]: { ...all[provider], [field]: value } })); };
  const connectionPayload = () => ({ provider, model: current.model.trim(), base_url: current.base_url.trim(), api_key: provider === "ollama" ? undefined : key || undefined, deadline_seconds: provider === "ollama" ? current.deadline_seconds ?? 300 : undefined });
  const testConnection = async () => {
    setPending(true); setTesting(true); setError(""); setTestResult(null);
    try {
      const result = await api<AIConnectionTest>("/settings/ai/test", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(connectionPayload()) });
      setTestResult(result);
    } catch (problem) { setError(problem instanceof Error ? problem.message : "Connection test failed."); }
    finally { setPending(false); setTesting(false); }
  };
  const save = async (disconnect = false) => {
    setPending(true); setError("");
    try {
      await api<AISettings>("/settings/ai", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ provider, model: current.model.trim(), base_url: current.base_url.trim(), api_key: provider === "ollama" ? undefined : disconnect ? "" : key || undefined, deadline_seconds: provider === "ollama" ? current.deadline_seconds ?? 300 : undefined }) });
      setKey(""); onSaved();
    } catch (problem) { setError(problem instanceof Error ? problem.message : "Could not save provider settings."); }
    finally { setPending(false); }
  };
  return <form className="ai-settings-form" onSubmit={event => { event.preventDefault(); void save(); }}>
    <p className="helper-text">{provider === "ollama" ? "Connect a downloaded local model to KnowGraph’s evidence tools. No API key is needed." : "Connect your model to KnowGraph’s evidence tools. Your API key is sent to the backend and is never returned to the browser."}</p>
    <label>AI provider<select aria-label="AI provider" value={provider} disabled={pending} onChange={event => { setProvider(event.target.value as Provider); setKey(""); setError(""); setTestResult(null); }}><option value="openai">OpenAI</option><option value="agentrouter">Agent Router / DeepSeek</option><option value="gemini">Google Gemini</option><option value="ollama">Local Ollama</option></select></label>
    {provider === "agentrouter" && <><label>API base URL<input type="url" aria-label="Agent Router API base URL" placeholder="https://agentrouter.org/v1" value={current.base_url} onChange={event => update("base_url", event.target.value)} required maxLength={2048} disabled={pending} /><small>For agentrouter.org use https://agentrouter.org/v1. Other routers: copy the OpenAI-compatible API base URL from your dashboard.</small></label><p className="helper-text">Your router must allow API access from custom applications. If the test reports “unauthorized client detected”, ask the router’s support to enable access for KnowGraph.</p></>}
    {provider === "ollama" && <><label>Ollama API base URL<input type="url" aria-label="Ollama API base URL" placeholder="http://127.0.0.1:11434/v1" value={current.base_url} onChange={event => update("base_url", event.target.value)} required maxLength={2048} disabled={pending} /><small>Use the URL reachable from the backend. Docker Desktop: host.docker.internal; optional Compose service: ollama.</small></label><div className="settings-storage-note"><ShieldCheck size={16} /><div><p>Start Ollama and download a model with tool support before chatting. For the starter model:</p><code>ollama pull qwen3:4b</code><p><a className="text-button" href="https://github.com/krshn0x/KnowGraph-AI-Standalone#run-local-ai-with-ollama" target="_blank" rel="noreferrer">Local setup instructions</a></p></div></div></>}
    {provider === "gemini" && <div className="settings-storage-note"><ShieldCheck size={16} /><div><p>Gemini 3.8 Flash has a free tier. Your Google project’s quotas and billing settings apply. KnowGraph does not switch to another provider when quota runs out.</p><a className="text-button" href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">Get a Gemini API key</a><span> · </span><a className="text-button" href="https://ai.google.dev/gemini-api/docs/pricing#gemini-3.8-flash" target="_blank" rel="noreferrer">Pricing & limits</a></div></div>}
    <label>Model ID<input aria-label="AI model ID" placeholder={provider === "agentrouter" ? "Exact DeepSeek V4 model ID from your dashboard" : provider === "gemini" ? "gemini-3.8-flash" : provider === "ollama" ? "qwen3:4b" : "gpt-6.1-sol"} value={current.model} onChange={event => update("model", event.target.value)} required maxLength={200} disabled={pending} /></label>
    {provider === "ollama" && <label>Investigation deadline (seconds)<input type="number" aria-label="Ollama investigation deadline" min={1} max={900} step={1} value={current.deadline_seconds ?? 300} onChange={event => setValues(all => ({ ...all, ollama: { ...all.ollama, deadline_seconds: Number(event.target.value) } }))} required disabled={pending} /><small>Includes model loading and every graph tool round trip. Default: 300 seconds; maximum: 900.</small></label>}
    {provider !== "ollama" && <label><span><KeyRound size={13} />API key{current.has_api_key && <span className="settings-key-saved">Saved on backend</span>}</span><input type="password" aria-label="Provider API key" autoComplete="off" autoCapitalize="none" spellCheck={false} placeholder={current.has_api_key ? "Leave blank to keep the saved key" : "Paste your provider API key"} value={key} onChange={event => { setKey(event.target.value); setTestResult(null); }} maxLength={4096} disabled={pending} required={!current.has_api_key} /></label>}
    <div className="settings-storage-note"><ShieldCheck size={16} /><p>Saved for this backend session. A backend restart restores the configuration from .env. Saving does not test model access or send an AI question.</p></div>
    {error && <ErrorNotice message={error} />}
    {testResult && (testResult.ok ? <div className="settings-storage-note" role="status"><ShieldCheck size={16} /><p>{testResult.message}</p></div> : <ErrorNotice message={testResult.message} />)}
    <p className="helper-text">Test connection runs a small graph question using these form values. It can take up to 90 seconds and uses your model quota. Save settings after a successful test.</p>
    <button className="button secondary" type="button" disabled={pending} onClick={event => { if (event.currentTarget.form?.reportValidity()) void testConnection(); }}><Network size={14} />{testing ? "Testing connection…" : "Test connection"}</button>
    <div className="settings-form-actions">{current.has_api_key && <button className="text-button" type="button" disabled={pending} onClick={() => void save(true)}><Unplug size={13} />Disconnect provider</button>}<button className="button primary" type="submit" disabled={pending}><Save size={14} />{pending && !testing ? "Saving…" : "Save AI settings"}</button></div>
  </form>;
}
