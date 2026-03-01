"use client";

import { useEffect, useState } from "react";

interface ModelInfo {
  id: string;
  name: string;
  description: string;
  size?: string;
}

interface ModelSettings {
  whisper_model: string;
  whisper_compute_type: string;
  ollama_model: string;
  embedding_model: string;
}

export default function SettingsPage() {
  const [models, setModels] = useState<{ transcription_models: ModelInfo[]; summarization_models: ModelInfo[] } | null>(null);
  const [currentSettings, setCurrentSettings] = useState<ModelSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/api/v1/settings/models`).then(r => r.json()),
      fetch(`${API_URL}/api/v1/settings/models/current`).then(r => r.json())
    ]).then(([modelsData, settingsData]) => {
      setModels(modelsData);
      setCurrentSettings(settingsData);
      setLoading(false);
    });
  }, []);

  const saveSettings = async () => {
    if (!currentSettings) return;
    setSaving(true);
    setMessage("");
    
    try {
      const response = await fetch(`${API_URL}/api/v1/settings/models`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentSettings)
      });
      
      if (response.ok) {
        setMessage("Settings saved! Restart required for changes to take effect.");
      } else {
        setMessage("Error saving settings");
      }
    } catch (e) {
      setMessage("Error saving settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-center">Loading...</div>;

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Settings</h1>
      <p className="text-gray-600 mb-8">Configure AI models for transcription and summarization</p>

      {message && (
        <div className={`p-4 rounded-lg mb-6 ${message.includes("Error") ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}`}>
          {message}
        </div>
      )}

      <div className="space-y-6">
        {/* Transcription Models */}
        <div className="bg-white rounded-lg border p-6">
          <h2 className="text-xl font-semibold mb-4">Transcription Model (Whisper)</h2>
          
          <div className="space-y-3">
            {models?.transcription_models.map((model) => (
              <label key={model.id} className="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
                <input
                  type="radio"
                  name="whisper_model"
                  value={model.id}
                  checked={currentSettings?.whisper_model === model.id}
                  onChange={(e) => setCurrentSettings({ ...currentSettings!, whisper_model: e.target.value })}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="flex justify-between">
                    <span className="font-medium">{model.name}</span>
                    {model.size && <span className="text-sm text-gray-500">{model.size}</span>}
                  </div>
                  <p className="text-sm text-gray-600">{model.description}</p>
                </div>
              </label>
            ))}
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">Compute Type</label>
            <select
              value={currentSettings?.whisper_compute_type}
              onChange={(e) => setCurrentSettings({ ...currentSettings!, whisper_compute_type: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="float16">Float16 (Faster)</option>
              <option value="float32">Float32 (More accurate)</option>
              <option value="int8">Int8 (Fastest)</option>
            </select>
          </div>
        </div>

        {/* Summarization Models */}
        <div className="bg-white rounded-lg border p-6">
          <h2 className="text-xl font-semibold mb-4">Summarization Model (Ollama)</h2>
          
          <div className="space-y-3">
            {models?.summarization_models.map((model) => (
              <label key={model.id} className="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
                <input
                  type="radio"
                  name="ollama_model"
                  value={model.id}
                  checked={currentSettings?.ollama_model === model.id}
                  onChange={(e) => setCurrentSettings({ ...currentSettings!, ollama_model: e.target.value })}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="flex justify-between">
                    <span className="font-medium">{model.name}</span>
                    {model.size && <span className="text-sm text-gray-500">{model.size}</span>}
                  </div>
                  <p className="text-sm text-gray-600">{model.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            onClick={saveSettings}
            disabled={saving}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </div>
    </main>
  );
}
