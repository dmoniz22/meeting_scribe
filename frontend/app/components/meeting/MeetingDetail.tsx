"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { ArrowLeft, Play, Pause, FileText, Sparkles, Loader2 } from "lucide-react";
import Card from "../ui/Card";
import Button from "../ui/Button";
import Badge from "../ui/Badge";
import { formatTime, formatDateTime } from "@/app/lib/format";
import { API_URL, STATUS_CONFIG, NOTE_TYPES } from "@/app/lib/constants";
import { recordingsApi } from "@/app/lib/api";
import type { Meeting, Note, TranscriptSegment, Summary } from "@/app/lib/constants";

interface MeetingDetailProps {
  meetingId: string;
}

type TabType = "transcript" | "summary" | "notes";

export default function MeetingDetail({ meetingId }: MeetingDetailProps) {
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("transcript");
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);

  // Note form state
  const [noteContent, setNoteContent] = useState("");
  const [noteType, setNoteType] = useState("general");
  const [addingNote, setAddingNote] = useState(false);

  // Transcription/summarization state
  const [transcribing, setTranscribing] = useState(false);
  const [summarizing, setSummarizing] = useState(false);

  const API_URL_VALUE = API_URL;

  useEffect(() => {
    fetchMeeting();
  }, [meetingId]);

  const fetchMeeting = async () => {
    try {
      const response = await fetch(`${API_URL_VALUE}/api/v1/meetings/${meetingId}/detail`);
      if (!response.ok) throw new Error("Failed to fetch meeting");
      const data = await response.json();
      setMeeting(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const addNote = async () => {
    if (!noteContent.trim()) return;

    setAddingNote(true);
    try {
      const response = await fetch(`${API_URL_VALUE}/api/v1/meetings/${meetingId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: noteContent,
          recording_offset: Math.floor(currentTime),
          note_type: noteType,
        }),
      });
      if (!response.ok) throw new Error("Failed to add note");

      setNoteContent("");
      fetchMeeting();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add note");
    } finally {
      setAddingNote(false);
    }
  };

  const deleteNote = async (noteId: string) => {
    if (!confirm("Delete this note?")) return;

    try {
      const response = await fetch(
        `${API_URL_VALUE}/api/v1/meetings/${meetingId}/notes/${noteId}`,
        { method: "DELETE" }
      );
      if (!response.ok) throw new Error("Failed to delete note");
      fetchMeeting();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete note");
    }
  };

  const handleTranscribe = async () => {
    setTranscribing(true);
    setError(null);
    try {
      const { data, error } = await recordingsApi.transcribe(meetingId);
      if (error) throw new Error(error);
      setMeeting((prev) => prev ? { ...prev, status: "transcribing" } : prev);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start transcription");
    } finally {
      setTranscribing(false);
    }
  };

  const handleSummarize = async () => {
    setSummarizing(true);
    setError(null);
    try {
      const { data, error } = await recordingsApi.summarize(meetingId);
      if (error) throw new Error(error);
      setMeeting((prev) => prev ? { ...prev, status: "summarizing" } : prev);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start summarization");
    } finally {
      setSummarizing(false);
    }
  };

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const seekTo = (time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
      if (!isPlaying) {
        audioRef.current.play();
        setIsPlaying(true);
      }
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleAudioEnded = () => {
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const getNoteTypeConfig = (type: string) =>
    NOTE_TYPES.find((t) => t.id === type) || NOTE_TYPES[0];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Error: {error}</p>
        <Button onClick={fetchMeeting} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  if (!meeting) {
    return <div className="text-center py-12">Meeting not found</div>;
  }

  const statusConfig = STATUS_CONFIG[meeting.status] || STATUS_CONFIG.idle;
  const audioUrl = meeting.audio_path
    ? `${API_URL_VALUE}/api/v1/recordings/audio/${meetingId}`
    : null;

  return (
    <div>
      <Link
        href="/"
        className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4"
      >
        <ArrowLeft className="w-4 h-4 mr-1" />
        Back to meetings
      </Link>

      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-3xl font-bold text-slate-900">{meeting.title}</h1>
          <Badge color={statusConfig.color}>{statusConfig.label}</Badge>
        </div>
        <p className="text-slate-500">
          {formatDateTime(meeting.created_at)}
          {meeting.duration_seconds && ` • ${formatTime(meeting.duration_seconds)}`}
        </p>
        {/* Action buttons */}
        {meeting.audio_path && (
          <div className="flex gap-3 mt-4">
            {(meeting.status === "recorded" || meeting.status === "transcribed" || meeting.status === "completed") && !meeting.transcript_segments?.length && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleTranscribe}
                disabled={transcribing}
                leftIcon={transcribing ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              >
                {transcribing ? "Transcribing..." : "Transcribe"}
              </Button>
            )}
            {(meeting.status === "transcribed" || meeting.status === "completed") && meeting.transcript_segments?.length && !meeting.summary && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleSummarize}
                disabled={summarizing}
                leftIcon={summarizing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              >
                {summarizing ? "Summarizing..." : "Summarize"}
              </Button>
            )}
            {meeting.status === "transcribing" && (
              <div className="flex items-center gap-2 text-amber-600 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                Transcription in progress...
              </div>
            )}
            {meeting.status === "summarizing" && (
              <div className="flex items-center gap-2 text-purple-600 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                Summarization in progress...
              </div>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Audio Player */}
      {audioUrl && (
        <Card className="mb-6">
          <div className="flex items-center gap-4">
            <button
              onClick={togglePlay}
              className="w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 transition-colors"
            >
              {isPlaying ? (
                <Pause className="w-5 h-5" />
              ) : (
                <Play className="w-5 h-5 ml-0.5" />
              )}
            </button>
            <div className="flex-1">
              <input
                type="range"
                min={0}
                max={meeting.duration_seconds || 100}
                value={currentTime}
                onChange={(e) => seekTo(parseFloat(e.target.value))}
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-sm text-slate-500 mt-1">
                <span>{formatTime(currentTime)}</span>
                <span>{formatTime(meeting.duration_seconds || 0)}</span>
              </div>
            </div>
          </div>
          <audio
            ref={audioRef}
            src={audioUrl}
            onTimeUpdate={handleTimeUpdate}
            onEnded={handleAudioEnded}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            className="hidden"
          />
        </Card>
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200 mb-4">
        <nav className="flex gap-6">
          {(["transcript", "summary", "notes"] as TabType[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 px-1 capitalize font-medium transition-colors ${
                activeTab === tab
                  ? "border-b-2 border-blue-600 text-blue-600"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab}
              {tab === "notes" && (meeting.notes?.length ?? 0) > 0 && (
                <span className="ml-2 bg-slate-200 text-slate-700 text-xs px-2 py-0.5 rounded-full">
                  {meeting.notes?.length ?? 0}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Transcript Tab */}
      {activeTab === "transcript" && (
        <Card padding="none">
          {!meeting.transcript_segments?.length ? (
            <div className="p-8 text-center text-slate-500">
              {meeting.status === "transcribing"
                ? "Transcription in progress..."
                : "No transcript available"}
            </div>
          ) : (
            <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
              {meeting.transcript_segments?.map((seg) => (
                <div
                  key={seg.id}
                  className="p-4 hover:bg-slate-50 cursor-pointer transition-colors"
                  onClick={() => seekTo(seg.start_time)}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-blue-600">
                      {seg.speaker_label || seg.speaker_name || "Speaker"}
                    </span>
                    <span className="text-xs text-slate-400">
                      {formatTime(seg.start_time)} - {formatTime(seg.end_time)}
                    </span>
                  </div>
                  <p className="text-slate-700">{seg.text}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Summary Tab */}
      {activeTab === "summary" && (
        <Card>
          {meeting.summary ? (
            <div>
              <h3 className="font-semibold text-lg mb-3">Summary</h3>
              <p className="text-slate-700 mb-6 whitespace-pre-wrap">
                {meeting.summary.summary_text}
              </p>

              {meeting.summary.key_decisions?.length > 0 && (
                <div className="mb-4">
                  <h4 className="font-medium mb-2 text-emerald-700">Key Decisions</h4>
                  <ul className="space-y-2">
                    {meeting.summary.key_decisions.map((d, i) => (
                      <li key={i} className="flex gap-2 text-slate-700">
                        <span className="text-emerald-600">✓</span>
                        <span>{d.text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {meeting.summary.action_items?.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2 text-blue-700">Action Items</h4>
                  <ul className="space-y-2">
                    {meeting.summary.action_items.map((item, i) => (
                      <li key={i} className="flex gap-2 text-slate-700">
                        <span className="text-blue-600">☐</span>
                        <span>{item.text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center text-slate-500 py-8">
              {meeting.status === "summarizing"
                ? "Summary being generated..."
                : "No summary available"}
            </div>
          )}
        </Card>
      )}

      {/* Notes Tab */}
      {activeTab === "notes" && (
        <div className="space-y-4">
          {/* Add Note Form */}
          <Card>
            <h3 className="font-medium text-slate-900 mb-3">
              Add Note @ {formatTime(currentTime)}
            </h3>
            <textarea
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              placeholder="Type your note here..."
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              rows={3}
            />
            <div className="flex justify-between items-center mt-3">
              <select
                value={noteType}
                onChange={(e) => setNoteType(e.target.value)}
                className="px-3 py-2 border border-slate-200 rounded-lg text-sm"
              >
                {NOTE_TYPES.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
              <Button
                onClick={addNote}
                disabled={addingNote || !noteContent.trim()}
                isLoading={addingNote}
              >
                Add Note
              </Button>
            </div>
          </Card>

          {/* Notes List */}
          {!meeting.notes?.length ? (
            <Card className="text-center text-slate-500">
              No notes yet. Add one above!
            </Card>
          ) : (
            <div className="space-y-3">
              {meeting.notes?.map((note) => {
                const typeConfig = getNoteTypeConfig(note.note_type);
                return (
                  <Card key={note.id} className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge color={typeConfig.color}>{typeConfig.label}</Badge>
                        <span className="text-xs text-slate-400">
                          @{formatTime(note.recording_offset)} •{" "}
                          {formatDateTime(note.created_at)}
                        </span>
                      </div>
                      <p className="text-slate-700">{note.content}</p>
                    </div>
                    <div className="flex gap-2 ml-4">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => seekTo(note.recording_offset)}
                      >
                        Jump
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteNote(note.id)}
                        className="text-rose-600 hover:bg-rose-50"
                      >
                        Delete
                      </Button>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
