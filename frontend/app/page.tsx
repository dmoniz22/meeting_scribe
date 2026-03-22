"use client";

import { useEffect, useState } from "react";
import RecordingCard from "./components/dashboard/RecordingCard";
import LiveNotes from "./components/dashboard/LiveNotes";
import MeetingsList from "./components/dashboard/MeetingsList";
import { meetingsApi, recordingsApi, daemonApi } from "./lib/api";
import type { Meeting, RecordingStatus, Note } from "./lib/constants";

export default function Dashboard() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recordingStatus, setRecordingStatus] = useState<RecordingStatus | null>(null);
  const [recordingLoading, setRecordingLoading] = useState(false);
  const [liveNotes, setLiveNotes] = useState<Note[]>([]);
  const [daemonStatus, setDaemonStatus] = useState<{ status: string; error?: string } | null>(null);
  const [daemonLoading, setDaemonLoading] = useState(false);
  const [systemGain, setSystemGain] = useState(0.5);
  const [micGain, setMicGain] = useState(10.0);
  const [showSettings, setShowSettings] = useState(false);

  // Fetch initial data
  useEffect(() => {
    fetchMeetings();
    fetchRecordingStatus();
    fetchDaemonStatus();
    fetchDaemonConfig();
  }, []);

  // Poll recording status every 2 seconds
  useEffect(() => {
    const interval = setInterval(fetchRecordingStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  // Poll daemon status every 5 seconds
  useEffect(() => {
    const interval = setInterval(fetchDaemonStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch live notes when recording
  useEffect(() => {
    if (recordingStatus?.is_recording && recordingStatus.meeting_id) {
      fetchLiveNotes();
      const interval = setInterval(fetchLiveNotes, 3000);
      return () => clearInterval(interval);
    } else {
      setLiveNotes([]);
    }
  }, [recordingStatus?.is_recording, recordingStatus?.meeting_id]);

  const fetchMeetings = async () => {
    try {
      setLoading(true);
      const { data, error } = await meetingsApi.getAll();
      if (error) throw new Error(error);
      setMeetings(data?.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch meetings");
    } finally {
      setLoading(false);
    }
  };

  const fetchRecordingStatus = async () => {
    try {
      const { data } = await recordingsApi.getStatus();
      setRecordingStatus(data);
    } catch {
      // Backend not available - silent fail
    }
  };

  const fetchDaemonStatus = async () => {
    try {
      const { data } = await daemonApi.status();
      setDaemonStatus(data);
    } catch (err) {
      setDaemonStatus({ status: "error", error: err instanceof Error ? err.message : "Unknown error" });
    }
  };

  const fetchDaemonConfig = async () => {
    try {
      const { data } = await daemonApi.getConfig();
      if (data) {
        setSystemGain(data.system_gain);
        setMicGain(data.mic_gain);
      }
    } catch {
      // Silent fail
    }
  };

  useEffect(() => {
    fetchDaemonConfig();
  }, []);

  const handleStartDaemon = async () => {
    setDaemonLoading(true);
    setError(null);
    try {
      const { error } = await daemonApi.start();
      if (error) throw new Error(error);
      await fetchDaemonStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start audio daemon");
    } finally {
      setDaemonLoading(false);
    }
  };

  const handleGainChange = async (newSystemGain: number, newMicGain: number) => {
    setSystemGain(newSystemGain);
    setMicGain(newMicGain);
    await daemonApi.setConfig(newSystemGain, newMicGain);
  };

  const handleRestartDaemon = async () => {
    setDaemonLoading(true);
    setError(null);
    try {
      const { data, error } = await daemonApi.restart();
      if (error) throw new Error(error);
      await fetchDaemonStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restart audio daemon");
    } finally {
      setDaemonLoading(false);
    }
  };

  const fetchLiveNotes = async () => {
    if (!recordingStatus?.meeting_id) return;
    try {
      const { data } = await meetingsApi.getNotes(recordingStatus.meeting_id);
      if (data) setLiveNotes(data);
    } catch {
      // Silent fail
    }
  };

  const handleStartRecording = async () => {
    setRecordingLoading(true);
    setError(null);
    try {
      const { error } = await recordingsApi.start();
      if (error) throw new Error(error);
      await fetchRecordingStatus();
      setTimeout(fetchMeetings, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start recording");
    } finally {
      setRecordingLoading(false);
    }
  };

  const handleStopRecording = async () => {
    setRecordingLoading(true);
    try {
      await recordingsApi.stop();
      await fetchRecordingStatus();
      setTimeout(fetchMeetings, 1000);
    } catch (err) {
      setError("Failed to stop recording");
    } finally {
      setRecordingLoading(false);
    }
  };

  const handleAddLiveNote = async (content: string, noteType: string) => {
    if (!recordingStatus?.meeting_id) return;
    const { error } = await meetingsApi.addNote(
      recordingStatus.meeting_id,
      content,
      recordingStatus.duration_seconds || 0,
      noteType
    );
    if (error) {
      setError(error);
    } else {
      await fetchLiveNotes();
    }
  };

  const handleDeleteMeeting = async (id: string) => {
    const { error } = await meetingsApi.delete(id);
    if (error) {
      setError(error);
    } else {
      await fetchMeetings();
    }
  };

  return (
    <div>
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-500 mt-1">Manage your meetings and recordings</p>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl flex items-center gap-3">
          <span className="font-medium">Error:</span> {error}
          <button
            onClick={() => setError(null)}
            className="ml-auto text-sm hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Audio Daemon Status */}
      <div className="mb-6 bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${daemonStatus?.status === "running" ? "bg-green-500" : "bg-red-500"}`}></div>
          <span className="font-medium text-slate-700">Audio Daemon:</span>
          <span className={`text-sm ${daemonStatus?.status === "running" ? "text-green-600" : "text-red-600"}`}>
            {daemonStatus?.status === "running" ? "Running" : daemonStatus?.status === "error" ? "Error" : "Stopped"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {daemonStatus?.status === "running" ? (
            <>
              <button
                onClick={handleRestartDaemon}
                disabled={daemonLoading || recordingStatus?.is_recording}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                title="Restart audio routing (re-setup capture paths)"
              >
                {daemonLoading ? "Restarting..." : "Restart Routing"}
              </button>
              <button
                onClick={handleStartDaemon}
                disabled={daemonLoading}
                className="px-4 py-2 bg-slate-800 text-white rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
                title="Restart the audio daemon"
              >
                {daemonLoading ? "Restarting..." : "Restart Daemon"}
              </button>
            </>
          ) : (
            <button
              onClick={handleStartDaemon}
              disabled={daemonLoading}
              className="px-4 py-2 bg-slate-800 text-white rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
            >
              {daemonLoading ? "Starting..." : "Start Daemon"}
            </button>
          )}
        </div>
      </div>

      {/* Audio Settings */}
      <div className="mb-6 bg-slate-50 border border-slate-200 rounded-xl p-4">
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="w-full flex items-center justify-between text-left"
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-700">Audio Settings</span>
          </div>
          <span className="text-sm text-slate-400">{showSettings ? "▲" : "▼"}</span>
        </button>
        {showSettings && (
          <div className="mt-4 space-y-4">
            {/* Level Meters */}
            {recordingStatus?.is_recording && (
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <div className="flex justify-between text-xs text-slate-500 mb-1">
                    <span>System Audio</span>
                    <span>{recordingStatus.rms_system?.toFixed(4) || "0.0000"}</span>
                  </div>
                  <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full transition-all"
                      style={{ width: `${Math.min((recordingStatus.rms_system || 0) * 500, 100)}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs text-slate-500 mb-1">
                    <span>Microphone</span>
                    <span>{recordingStatus.rms_mic?.toFixed(4) || "0.0000"}</span>
                  </div>
                  <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-rose-500 rounded-full transition-all"
                      style={{ width: `${Math.min((recordingStatus.rms_mic || 0) * 500, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            )}
            {/* System Gain */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-600">System Audio Gain</span>
                <span className="text-slate-800 font-mono">{systemGain.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="2.0"
                step="0.05"
                value={systemGain}
                onChange={(e) => handleGainChange(parseFloat(e.target.value), micGain)}
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <div className="flex justify-between text-xs text-slate-400 mt-1">
                <span>Quieter</span>
                <span>Louder</span>
              </div>
            </div>
            {/* Mic Gain */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-600">Microphone Gain</span>
                <span className="text-slate-800 font-mono">{micGain.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="1.0"
                max="30.0"
                step="0.5"
                value={micGain}
                onChange={(e) => handleGainChange(systemGain, parseFloat(e.target.value))}
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-rose-600"
              />
              <div className="flex justify-between text-xs text-slate-400 mt-1">
                <span>Quieter</span>
                <span>Louder</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Recording Control */}
      <RecordingCard
        status={recordingStatus}
        onStart={handleStartRecording}
        onStop={handleStopRecording}
        loading={recordingLoading}
      />

      {/* Live Notes (only when recording) */}
      {recordingStatus?.is_recording && recordingStatus.meeting_id && (
        <LiveNotes
          recordingStatus={recordingStatus}
          notes={liveNotes}
          onAddNote={handleAddLiveNote}
        />
      )}

      {/* Meetings List */}
      <MeetingsList
        meetings={meetings}
        loading={loading}
        onDelete={handleDeleteMeeting}
      />
    </div>
  );
}
