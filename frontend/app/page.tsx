"use client";

import { useEffect, useState } from "react";
import RecordingCard from "./components/dashboard/RecordingCard";
import LiveNotes from "./components/dashboard/LiveNotes";
import MeetingsList from "./components/dashboard/MeetingsList";
import { meetingsApi, recordingsApi } from "./lib/api";
import type { Meeting, RecordingStatus, Note } from "./lib/constants";

export default function Dashboard() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recordingStatus, setRecordingStatus] = useState<RecordingStatus | null>(null);
  const [recordingLoading, setRecordingLoading] = useState(false);
  const [liveNotes, setLiveNotes] = useState<Note[]>([]);

  // Fetch initial data
  useEffect(() => {
    fetchMeetings();
    fetchRecordingStatus();
  }, []);

  // Poll recording status every 2 seconds
  useEffect(() => {
    const interval = setInterval(fetchRecordingStatus, 2000);
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
