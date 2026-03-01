"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Mic,
  MicOff,
  Search,
  Filter,
  Clock,
  CalendarDays,
  Trash2,
  Plus,
  FileText,
  Play,
  CheckCircle2,
} from "lucide-react";

interface Meeting {
  id: string;
  title: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  created_at: string;
}

interface RecordingStatus {
  is_recording: boolean;
  meeting_id: string | null;
  started_at: string | null;
  duration_seconds: number | null;
}

interface Note {
  id: string;
  content: string;
  recording_offset: number;
  note_type: string;
  created_at: string;
}

const NOTE_TYPES = [
  { id: "general", label: "General", color: "bg-slate-100 text-slate-700", icon: FileText },
  { id: "action_item", label: "Action Item", color: "bg-blue-100 text-blue-700", icon: CheckCircle2 },
  { id: "decision", label: "Decision", color: "bg-emerald-100 text-emerald-700", icon: CheckCircle2 },
  { id: "question", label: "Question", color: "bg-amber-100 text-amber-700", icon: FileText },
];

export default function Home() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recordingStatus, setRecordingStatus] = useState<RecordingStatus | null>(null);
  const [recordingLoading, setRecordingLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [liveNotes, setLiveNotes] = useState<Note[]>([]);
  const [liveNoteContent, setLiveNoteContent] = useState("");
  const [liveNoteType, setLiveNoteType] = useState("general");
  const [addingLiveNote, setAddingLiveNote] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

  useEffect(() => {
    fetchMeetings();
    fetchRecordingStatus();
    const interval = setInterval(fetchRecordingStatus, 2000);
    return () => clearInterval(interval);
  }, []);

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
      const response = await fetch(`${API_URL}/api/v1/meetings`);
      if (!response.ok) throw new Error("Failed to fetch meetings");
      const data = await response.json();
      setMeetings(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const fetchRecordingStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/recordings/status`);
      if (response.ok) {
        const data = await response.json();
        setRecordingStatus(data);
      } else {
        // API not available - recording won't work
        console.log("Recording API not available");
      }
    } catch (err) {
      // Backend not running - recording won't work
      console.log("Backend API not reachable");
    }
  };

  const fetchLiveNotes = async () => {
    if (!recordingStatus?.meeting_id) return;
    try {
      const response = await fetch(`${API_URL}/api/v1/meetings/${recordingStatus.meeting_id}/notes`);
      if (response.ok) {
        const data = await response.json();
        setLiveNotes(data);
      }
    } catch (err) {}
  };

  const startRecording = async () => {
    setRecordingLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/api/v1/recordings/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meeting_id: null }),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Failed to start recording");
      }
      fetchRecordingStatus();
      setTimeout(fetchMeetings, 1000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start recording. Is the backend running?";
      setError(message);
    } finally {
      setRecordingLoading(false);
    }
  };

  const stopRecording = async () => {
    setRecordingLoading(true);
    try {
      await fetch(`${API_URL}/api/v1/recordings/stop`, { method: "POST" });
      fetchRecordingStatus();
      setTimeout(fetchMeetings, 1000);
    } catch (err) {
      setError("Failed to stop recording");
    } finally {
      setRecordingLoading(false);
    }
  };

  const addLiveNote = async () => {
    if (!liveNoteContent.trim() || !recordingStatus?.meeting_id) return;
    setAddingLiveNote(true);
    try {
      await fetch(`${API_URL}/api/v1/meetings/${recordingStatus.meeting_id}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: liveNoteContent,
          recording_offset: recordingStatus.duration_seconds || 0,
          note_type: liveNoteType,
        }),
      });
      setLiveNoteContent("");
      fetchLiveNotes();
    } catch (err) {
      setError("Failed to add note");
    } finally {
      setAddingLiveNote(false);
    }
  };

  const deleteMeeting = async (id: string) => {
    if (!confirm("Delete this meeting?")) return;
    try {
      await fetch(`${API_URL}/api/v1/meetings/${id}`, { method: "DELETE" });
      fetchMeetings();
    } catch (err) {
      setError("Failed to delete meeting");
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "—";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const getNoteTypeConfig = (type: string) => NOTE_TYPES.find(t => t.id === type) || NOTE_TYPES[0];

  const filteredMeetings = meetings
    .filter((m) => statusFilter === "all" || m.status === statusFilter)
    .filter((m) => !searchQuery || m.title.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">Manage your meetings and recordings</p>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl flex items-center gap-3">
          <span className="font-medium">Error:</span> {error}
        </div>
      )}

      {/* Recording Control Card */}
      <div className="mb-8 bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        {recordingStatus?.is_recording ? (
          <>
            <div className="bg-gradient-to-r from-rose-500 to-red-600 p-6 text-white">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <span className="animate-ping absolute inline-flex h-4 w-4 rounded-full bg-white opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-4 w-4 bg-white"></span>
                  </div>
                  <div>
                    <p className="text-rose-100 text-sm font-medium">Recording in Progress</p>
                    <p className="text-4xl font-bold font-mono">{formatDuration(recordingStatus.duration_seconds || 0)}</p>
                  </div>
                </div>
                <button
                  onClick={stopRecording}
                  disabled={recordingLoading}
                  className="bg-white text-rose-600 px-8 py-4 rounded-xl font-semibold hover:bg-rose-50 disabled:opacity-50 transition-colors shadow-lg flex items-center gap-2"
                >
                  <MicOff className="w-5 h-5" />
                  {recordingLoading ? "Stopping..." : "Stop Recording"}
                </button>
              </div>
            </div>

            {/* Live Notes Section */}
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-gray-400" />
                  Live Notes ({liveNotes.length})
                </h3>
                <span className="text-sm text-gray-500">Take notes while recording</span>
              </div>
              
              <div className="flex gap-4 mb-4">
                <div className="flex-1">
                  <textarea
                    placeholder="Type your note here... Press Ctrl+Enter to save"
                    value={liveNoteContent}
                    onChange={(e) => setLiveNoteContent(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && e.ctrlKey) {
                        e.preventDefault();
                        addLiveNote();
                      }
                    }}
                    rows={4}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none text-base leading-relaxed"
                  />
                  <p className="text-xs text-gray-400 mt-2">Ctrl+Enter to save • {liveNoteContent.length} characters</p>
                </div>
                <div className="flex flex-col gap-2 w-40">
                  <select
                    value={liveNoteType}
                    onChange={(e) => setLiveNoteType(e.target.value)}
                    className="px-4 py-3 border border-gray-200 rounded-xl text-sm bg-white"
                  >
                    {NOTE_TYPES.map(t => (
                      <option key={t.id} value={t.id}>{t.label}</option>
                    ))}
                  </select>
                  <button
                    onClick={addLiveNote}
                    disabled={addingLiveNote || !liveNoteContent.trim()}
                    className="bg-blue-600 text-white px-4 py-3 rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                  >
                    <Plus className="w-4 h-4" />
                    {addingLiveNote ? "Saving..." : "Add Note"}
                  </button>
                </div>
              </div>

              {/* Notes List */}
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {liveNotes.length === 0 ? (
                  <div className="text-center py-8 bg-gray-50 rounded-xl">
                    <FileText className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    <p className="text-gray-500 text-sm">No notes yet. Start typing above!</p>
                  </div>
                ) : (
                  liveNotes.map((note) => {
                    const typeConfig = getNoteTypeConfig(note.note_type);
                    const Icon = typeConfig.icon;
                    return (
                      <div key={note.id} className="flex items-start gap-3 p-4 bg-gray-50 rounded-xl">
                        <span className={`text-xs px-3 py-1.5 rounded-lg font-medium flex items-center gap-1.5 ${typeConfig.color}`}>
                          <Icon className="w-3 h-3" />
                          {typeConfig.label}
                        </span>
                        <span className="text-xs text-gray-400 font-mono mt-1.5">
                          {formatDuration(note.recording_offset)}
                        </span>
                        <p className="text-gray-700 flex-1 text-sm">{note.content}</p>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="p-8 text-center">
            <div className="w-16 h-16 bg-gradient-to-br from-rose-500 to-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-rose-500/20">
              <Mic className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Ready to Record</h3>
            <p className="text-gray-500 mb-6 max-w-md mx-auto">
              Click below to start recording your meeting. You'll be able to take notes in real-time while the recording is active.
            </p>
            <button
              onClick={startRecording}
              disabled={recordingLoading}
              className="bg-gradient-to-r from-rose-500 to-red-600 text-white px-8 py-4 rounded-2xl font-semibold text-lg hover:shadow-xl hover:shadow-rose-500/25 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 transition-all flex items-center gap-3 mx-auto"
            >
              <Play className="w-5 h-5" />
              {recordingLoading ? "Starting..." : "Start Recording"}
            </button>
            {!recordingStatus && (
              <p className="text-xs text-amber-600 mt-4">
                Note: Make sure the backend API is running on port 8003
              </p>
            )}
          </div>
        )}
      </div>

      {/* Meetings List */}
      <div className="mb-6 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Recent Meetings</h2>
          <p className="text-sm text-gray-500">{filteredMeetings.length} meetings</p>
        </div>
        <div className="flex gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent w-48"
            />
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="pl-10 pr-8 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="all">All Status</option>
              <option value="idle">Idle</option>
              <option value="recording">Recording</option>
              <option value="processing">Processing</option>
              <option value="completed">Completed</option>
            </select>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        </div>
      ) : filteredMeetings.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-2xl border border-gray-200">
          <CalendarDays className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">No meetings found</p>
          <p className="text-sm text-gray-400 mt-1">Start your first recording above</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {filteredMeetings.map((meeting) => (
            <div key={meeting.id} className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-all group">
              <div className="flex items-center justify-between">
                <Link href={`/meetings/${meeting.id}`} className="flex-1">
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      meeting.status === "recording" ? "bg-rose-100" :
                      meeting.status === "processing" ? "bg-amber-100" :
                      meeting.status === "completed" ? "bg-emerald-100" :
                      "bg-slate-100"
                    }`}>
                      {meeting.status === "recording" ? (
                        <Mic className="w-5 h-5 text-rose-600" />
                      ) : meeting.status === "completed" ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                      ) : (
                        <FileText className="w-5 h-5 text-slate-600" />
                      )}
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
                        {meeting.title}
                      </h3>
                      <div className="flex items-center gap-3 text-sm text-gray-500">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          {formatDuration(meeting.duration_seconds)}
                        </span>
                        <span>•</span>
                        <span>{new Date(meeting.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                </Link>
                <div className="flex items-center gap-3">
                  <span className={`text-xs px-3 py-1.5 rounded-full font-medium ${
                    meeting.status === "recording" ? "bg-rose-100 text-rose-700" :
                    meeting.status === "processing" ? "bg-amber-100 text-amber-700" :
                    meeting.status === "completed" ? "bg-emerald-100 text-emerald-700" :
                    "bg-slate-100 text-slate-700"
                  }`}>
                    {meeting.status}
                  </span>
                  <button
                    onClick={() => deleteMeeting(meeting.id)}
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
