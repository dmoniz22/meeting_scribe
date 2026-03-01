"use client";

import { Settings, Info } from "lucide-react";
import Card from "../components/ui/Card";

export default function SettingsPage() {
  return (
    <div>
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-500 mt-1">Configure your MeetScribe preferences</p>
      </div>

      {/* Coming Soon */}
      <Card className="text-center py-16">
        <Settings className="w-16 h-16 text-slate-300 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-slate-900 mb-2">Settings Coming Soon</h2>
        <p className="text-slate-500 max-w-md mx-auto">
          This page will contain configuration options for the audio daemon,
          transcription settings, and export preferences.
        </p>
        
        <div className="mt-8 flex items-center justify-center gap-2 text-sm text-slate-400">
          <Info className="w-4 h-4" />
          <span>API connected to http://localhost:8003</span>
        </div>
      </Card>

      {/* Future Settings */}
      <div className="mt-8 grid gap-4">
        <Card>
          <h3 className="font-semibold text-slate-900 mb-2">Audio Settings</h3>
          <p className="text-slate-500 text-sm">Audio source selection, recording quality, and format options</p>
          <span className="inline-block mt-3 px-3 py-1 text-xs font-medium bg-slate-100 text-slate-600 rounded-full">
            Coming soon
          </span>
        </Card>

        <Card>
          <h3 className="font-semibold text-slate-900 mb-2">Transcription Settings</h3>
          <p className="text-slate-500 text-sm">Whisper model selection, language preferences, and speaker diarization</p>
          <span className="inline-block mt-3 px-3 py-1 text-xs font-medium bg-slate-100 text-slate-600 rounded-full">
            Coming soon
          </span>
        </Card>

        <Card>
          <h3 className="font-semibold text-slate-900 mb-2">Export Settings</h3>
          <p className="text-slate-500 text-sm">Default export format, naming conventions, and destination folder</p>
          <span className="inline-block mt-3 px-3 py-1 text-xs font-medium bg-slate-100 text-slate-600 rounded-full">
            Coming soon
          </span>
        </Card>
      </div>
    </div>
  );
}
