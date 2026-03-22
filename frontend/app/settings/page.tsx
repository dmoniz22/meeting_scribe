"use client";

import { useEffect, useState } from "react";
import {
  Settings,
  Eye,
  EyeOff,
  CheckCircle,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Download,
  ExternalLink,
} from "lucide-react";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";
import { settingsApi, type AppSettings, type ModelInfo } from "@/app/lib/api";
import { API_URL } from "@/app/lib/constants";

export default function SettingsPage() {
  const [data, setData] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [whisperModel, setWhisperModel] = useState("medium");
  const [whisperComputeType, setWhisperComputeType] = useState("float16");
  const [whisperBatchSize, setWhisperBatchSize] = useState(8);
  const [ollamaModel, setOllamaModel] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("");
  const [llmProvider, setLlmProvider] = useState("ollama");
  const [openrouterModel, setOpenrouterModel] = useState("");
  const [hfToken, setHfToken] = useState("");
  const [openrouterApiKey, setOpenrouterApiKey] = useState("");
  const [showHfToken, setShowHfToken] = useState(false);
  const [showOpenrouterKey, setShowOpenrouterKey] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    const { data, error } = await settingsApi.get();
    if (error) {
      setError(error);
    } else if (data) {
      setData(data);
      setWhisperModel(data.current.whisper_model);
      setWhisperComputeType(data.current.whisper_compute_type);
      setWhisperBatchSize(data.current.whisper_batch_size);
      setOllamaModel(data.current.ollama_model);
      setEmbeddingModel(data.current.embedding_model);
      setLlmProvider(data.current.llm_provider);
      setOpenrouterModel(data.current.openrouter_model);
    }
    setLoading(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setError(null);
    const update: Record<string, unknown> = {
      whisper_model: whisperModel,
      whisper_compute_type: whisperComputeType,
      whisper_batch_size: whisperBatchSize,
      ollama_model: ollamaModel,
      embedding_model: embeddingModel,
      llm_provider: llmProvider,
      openrouter_model: openrouterModel,
    };
    if (hfToken) update.hf_token = hfToken;
    if (openrouterApiKey) update.openrouter_api_key = openrouterApiKey;

    const { data, error } = await settingsApi.update(update);
    if (error) {
      setError(error);
    } else {
      if (data) setData(data);
      setSaved(true);
      setTimeout(() => setSaved(false), 5000);
    }
    setSaving(false);
  };

  const handleReset = () => {
    if (data) {
      setWhisperModel(data.current.whisper_model);
      setWhisperComputeType(data.current.whisper_compute_type);
      setWhisperBatchSize(data.current.whisper_batch_size);
      setOllamaModel(data.current.ollama_model);
      setEmbeddingModel(data.current.embedding_model);
      setLlmProvider(data.current.llm_provider);
      setOpenrouterModel(data.current.openrouter_model);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!data) {
    return <div className="text-red-600 p-8">Failed to load settings: {error}</div>;
  }

  return (
    <div>
      {/* Page Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
          <p className="text-slate-500 mt-1">Configure MeetScribe transcription and AI models</p>
        </div>
        <div className="flex items-center gap-3">
          {saved && (
            <span className="flex items-center gap-1 text-emerald-600 text-sm">
              <CheckCircle className="w-4 h-4" /> Saved
            </span>
          )}
          <Button variant="secondary" size="sm" onClick={handleReset}>Reset</Button>
          <Button size="sm" onClick={handleSave} disabled={saving} isLoading={saving}>
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}

      <div className="grid gap-6 max-w-4xl">
        {/* Dependency Status */}
        <Card>
          <h2 className="text-lg font-semibold text-slate-900 mb-1">System Status</h2>
          <p className="text-sm text-slate-500 mb-4">Dependencies and connections</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <DependencyItem label="Whisper" status={data.dependencies.whisperx} />
            <DependencyItem label="Speaker Diarization" status={data.dependencies.pyannote} />
            <DependencyItem label="Embeddings" status={data.dependencies.sentence_transformers} />
            <DependencyItem label="HuggingFace Token" status={data.dependencies.hf_token} />
            <DependencyItem label="Ollama Server" status={data.dependencies.ollama_reachable} />
            <DependencyItem label="OpenRouter Key" status={data.dependencies.openrouter_key} />
          </div>
        </Card>

        {/* Transcription Settings */}
        <Card>
          <h2 className="text-lg font-semibold text-slate-900 mb-1">Transcription</h2>
          <p className="text-sm text-slate-500 mb-4">
            Whisper model for speech-to-text. Models are downloaded from HuggingFace on first use.
          </p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Whisper Model</label>
              <select
                value={whisperModel}
                onChange={(e) => setWhisperModel(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {data.whisper_models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label} ({m.size}) {m.downloaded ? "  [Downloaded]" : ""}
                  </option>
                ))}
              </select>
              {!data.whisper_models.find((m) => m.id === whisperModel)?.downloaded && (
                <p className="mt-1 text-xs text-amber-600 flex items-center gap-1">
                  <Download className="w-3 h-3" /> This model will be downloaded from HuggingFace on first use (~{data.whisper_models.find((m) => m.id === whisperModel)?.size})
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Compute Type</label>
                <select
                  value={whisperComputeType}
                  onChange={(e) => setWhisperComputeType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="float16">Float16 (fastest, requires GPU)</option>
                  <option value="float32">Float32 (CPU compatible)</option>
                  <option value="int8">Int8 (lowest memory)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Batch Size</label>
                <select
                  value={whisperBatchSize}
                  onChange={(e) => setWhisperBatchSize(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {[1, 2, 4, 8, 16].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
            </div>

            {!data.dependencies.hf_token && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
                <strong>HuggingFace token required</strong> for speaker diarization (pyannote.audio).
                <br />
                1. Create an account at{" "}
                <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener noreferrer" className="underline">
                  huggingface.co
                </a>
                <br />
                2. Accept the{" "}
                <a href="https://huggingface.co/pyannote/speaker-diarization-3.1" target="_blank" rel="noopener noreferrer" className="underline">
                  pyannote terms
                </a>{" "}
                and{" "}
                <a href="https://huggingface.co/pyannote/segmentation-3.0" target="_blank" rel="noopener noreferrer" className="underline">
                  segmentation terms
                </a>
                <br />
                3. Paste your token below
              </div>
            )}
          </div>
        </Card>

        {/* Summarization Settings */}
        <Card>
          <h2 className="text-lg font-semibold text-slate-900 mb-1">Summarization</h2>
          <p className="text-sm text-slate-500 mb-4">LLM for generating meeting summaries and action items</p>

          <div className="space-y-4">
            {/* Provider selection */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">LLM Provider</label>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setLlmProvider("ollama")}
                  className={`flex-1 p-3 rounded-lg border-2 text-left transition-colors ${
                    llmProvider === "ollama"
                      ? "border-blue-500 bg-blue-50"
                      : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div className="font-medium text-sm">Local Ollama</div>
                  <div className="text-xs text-slate-500">Free, runs on your hardware</div>
                </button>
                <button
                  type="button"
                  onClick={() => setLlmProvider("openrouter")}
                  className={`flex-1 p-3 rounded-lg border-2 text-left transition-colors ${
                    llmProvider === "openrouter"
                      ? "border-blue-500 bg-blue-50"
                      : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div className="font-medium text-sm">OpenRouter (Cloud)</div>
                  <div className="text-xs text-slate-500">Access many models via API</div>
                </button>
              </div>
            </div>

            {llmProvider === "ollama" && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Ollama Model</label>
                {data.ollama_models.length > 0 ? (
                  <select
                    value={ollamaModel}
                    onChange={(e) => setOllamaModel(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    {data.ollama_models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label} {m.parameter_size ? `(${m.parameter_size})` : ""}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
                    <strong>No Ollama models found.</strong>
                    <br />
                    Pull a model with:{" "}
                    <code className="bg-white px-1 rounded">ollama pull llama3.1:8b</code>
                  </div>
                )}
                <p className="mt-1 text-xs text-slate-400">
                  Make sure Ollama is running:{" "}
                  <code className="bg-slate-100 px-1 rounded">ollama serve</code>
                </p>
              </div>
            )}

            {llmProvider === "openrouter" && (
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">OpenRouter Model</label>
                  <select
                    value={openrouterModel}
                    onChange={(e) => setOpenrouterModel(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    {data.openrouter_models.map((m) => (
                      <option key={m.id} value={m.id}>{m.label}</option>
                    ))}
                  </select>
                </div>
                {!data.dependencies.openrouter_key && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
                    <strong>OpenRouter API key required.</strong>
                    <br />
                    Get one at{" "}
                    <a href="https://openrouter.ai/settings/keys" target="_blank" rel="noopener noreferrer" className="underline">
                      openrouter.ai/settings/keys
                    </a>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* Embedding Settings */}
        <Card>
          <h2 className="text-lg font-semibold text-slate-900 mb-1">Embeddings</h2>
          <p className="text-sm text-slate-500 mb-4">
            Model for semantic search across meeting transcripts. Downloaded from HuggingFace.
          </p>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Embedding Model</label>
            <select
              value={embeddingModel}
              onChange={(e) => setEmbeddingModel(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {data.embedding_models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label} ({m.size}) {m.downloaded ? "  [Downloaded]" : ""}
                </option>
              ))}
            </select>
            {!data.embedding_models.find((m) => m.id === embeddingModel)?.downloaded && (
              <p className="mt-1 text-xs text-amber-600 flex items-center gap-1">
                <Download className="w-3 h-3" /> Will be downloaded from HuggingFace on first use
              </p>
            )}
          </div>
        </Card>

        {/* API Keys */}
        <Card>
          <h2 className="text-lg font-semibold text-slate-900 mb-1">API Keys</h2>
          <p className="text-sm text-slate-500 mb-4">Credentials for external services</p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">HuggingFace Token</label>
              <div className="relative">
                <input
                  type={showHfToken ? "text" : "password"}
                  value={hfToken}
                  onChange={(e) => setHfToken(e.target.value)}
                  placeholder="hf_xxxxxxxxxxxxx"
                  className="w-full px-3 py-2 pr-10 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowHfToken(!showHfToken)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showHfToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="mt-1 text-xs text-slate-400">
                Required for Whisper and speaker diarization. Get one at{" "}
                <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                  huggingface.co <ExternalLink className="w-3 h-3 inline" />
                </a>
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">OpenRouter API Key</label>
              <div className="relative">
                <input
                  type={showOpenrouterKey ? "text" : "password"}
                  value={openrouterApiKey}
                  onChange={(e) => setOpenrouterApiKey(e.target.value)}
                  placeholder="sk-or-..."
                  className="w-full px-3 py-2 pr-10 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowOpenrouterKey(!showOpenrouterKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showOpenrouterKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="mt-1 text-xs text-slate-400">
                For cloud LLM summarization. Get one at{" "}
                <a href="https://openrouter.ai/settings/keys" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                  openrouter.ai <ExternalLink className="w-3 h-3 inline" />
                </a>
              </p>
            </div>
          </div>
        </Card>

        {/* Info */}
        <Card className="bg-slate-50 border-slate-200">
          <div className="flex gap-3">
            <Settings className="w-5 h-5 text-slate-400 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-slate-600">
              <p>
                <strong>Whisper:</strong> Models download from HuggingFace on first transcription.{" "}
                <strong>Embeddings:</strong> Also from HuggingFace.{" "}
                <strong>Summarization:</strong> Uses your chosen provider (local Ollama or cloud OpenRouter).
              </p>
              <p className="mt-2">
                The backend will automatically restart when you save settings. API keys are persisted to the <code className="bg-white px-1 py-0.5 rounded border border-slate-200 text-xs">.env</code> file.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function DependencyItem({ label, status }: { label: string; status: boolean }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {status ? (
        <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
      ) : (
        <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />
      )}
      <span className={status ? "text-slate-700" : "text-amber-700"}>{label}</span>
    </div>
  );
}
