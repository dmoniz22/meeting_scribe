"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

interface Meeting {
  id: string;
  title: string;
  status: string;
  duration_seconds: number | null;
  audio_path: string | null;
  created_at: string;
  transcript_segments: any[];
  notes: any[];
  summary: any;
}

const NOTE_TYPES = [
  { id: "general", label: "General", color: "bg-gray-100 text-gray-800" },
  { id: "action_item", label: "Action Item", color: "bg-blue-100 text-blue-800" },
  { id: "decision", label: "Decision", color: "bg-green-100 text-green-800" },
  { id: "question", label: "Question", color: "bg-yellow-100 text-yellow-800" },
];

export default function MeetingDetailPage() {
  const params = useParams();
  const meetingId = params.id as string;
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("transcript");
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  
  // Note form state
  const [noteContent, setNoteContent] = useState("");
  const [noteType, setNoteType] = useState("general");
  const [addingNote, setAddingNote] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

  useEffect(() => {
    fetchMeeting();
  }, [meetingId]);

  const fetchMeeting = async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/meetings/${meetingId}/detail`);
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
      const response = await fetch(`${API_URL}/api/v1/meetings/${meetingId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: noteContent,
          recording_offset: currentTime,
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
        `${API_URL}/api/v1/meetings/${meetingId}/notes/${noteId}`,
        { method: "DELETE" }
      );
      if (!response.ok) throw new Error("Failed to delete note");
      fetchMeeting();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete note");
    }
  };

  const formatTime = (s: number) => `${Math.floor(s/60)}:${(s%60).toString().padStart(2,"0")}`;

  const getNoteTypeLabel = (type: string) => NOTE_TYPES.find(t => t.id === type)?.label || type;
  const getNoteTypeColor = (type: string) => NOTE_TYPES.find(t => t.id === type)?.color || "bg-gray-100";

  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;
  if (!meeting) return <div className="p-8">Meeting not found</div>;

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      <Link href="/" className="text-blue-600 hover:underline">← Back to meetings</Link>
      <h1 className="text-3xl font-bold mt-4 mb-2">{meeting.title}</h1>
      <p className="text-gray-500 mb-6">{new Date(meeting.created_at).toLocaleString()}</p>
      
      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
        </div>
      )}
      
      {/* Audio Player */}
      {meeting.audio_path && (
        <div className="bg-white border rounded-lg p-4 mb-6">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => {
                if (audioRef.current) {
                  if (isPlaying) audioRef.current.pause();
                  else audioRef.current.play();
                  setIsPlaying(!isPlaying);
                }
              }}
              className="bg-blue-600 text-white rounded-full w-12 h-12 flex items-center justify-center hover:bg-blue-700 text-xl"
            >
              {isPlaying ? "⏸" : "▶"}
            </button>
            <div className="flex-1">
              <input 
                type="range" 
                min={0} 
                max={meeting.duration_seconds || 100} 
                value={currentTime}
                onChange={(e) => {
                  const t = parseFloat(e.target.value);
                  setCurrentTime(t);
                  if (audioRef.current) audioRef.current.currentTime = t;
                }}
                className="w-full"
              />
              <div className="flex justify-between text-sm text-gray-500 mt-1">
                <span>{formatTime(currentTime)}</span>
                <span>{formatTime(meeting.duration_seconds || 0)}</span>
              </div>
            </div>
          </div>
          <audio 
            ref={audioRef}
            src={`${API_URL}/api/v1/recordings/audio/${meetingId}`}
            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
            onEnded={() => setIsPlaying(false)}
            className="hidden"
          />
        </div>
      )}

      {/* Tabs */}
      <div className="border-b mb-4">
        <nav className="flex gap-6">
          {["transcript", "summary", "notes"].map(tab => (
            <button 
              key={tab} 
              onClick={() => setActiveTab(tab)}
              className={`pb-3 px-1 capitalize font-medium ${activeTab === tab ? "border-b-2 border-blue-600 text-blue-600" : "text-gray-500 hover:text-gray-700"}`}
            >
              {tab}
              {tab === "notes" && meeting.notes?.length > 0 && (
                <span className="ml-2 bg-gray-200 text-gray-700 text-xs px-2 py-0.5 rounded-full">
                  {meeting.notes.length}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      {activeTab === "transcript" && (
        <div className="bg-white border rounded-lg">
          {meeting.transcript_segments?.length === 0 ? (
            <p className="p-8 text-center text-gray-500">
              {meeting.status === "processing" ? "Transcription in progress..." : "No transcript available"}
            </p>
          ) : (
            meeting.transcript_segments?.map((seg: any) => (
              <div key={seg.id} className="p-4 border-b hover:bg-gray-50 cursor-pointer"
                   onClick={() => { if (audioRef.current) { audioRef.current.currentTime = seg.start_time; audioRef.current.play(); setIsPlaying(true); }}}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm text-blue-600 font-medium">{seg.speaker_label || seg.speaker_name || "Speaker"}</span>
                  <span className="text-xs text-gray-400">{formatTime(seg.start_time)} - {formatTime(seg.end_time)}</span>
                </div>
                <p className="text-gray-700">{seg.text}</p>
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === "summary" && (
        <div className="bg-white border rounded-lg p-6">
          {meeting.summary ? (
            <div>
              <h3 className="font-semibold text-lg mb-3">Summary</h3>
              <p className="text-gray-700 mb-4">{meeting.summary.summary_text}</p>
              
              {meeting.summary.key_decisions?.length > 0 && (
                <div className="mb-4">
                  <h4 className="font-medium mb-2">Key Decisions</h4>
                  <ul className="space-y-1">
                    {meeting.summary.key_decisions.map((d: any, i: number) => (
                      <li key={i} className="flex gap-2"><span className="text-green-600">✓</span><span>{d.text}</span></li>
                    ))}
                  </ul>
                </div>
              )}
              
              {meeting.summary.action_items?.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2">Action Items</h4>
                  <ul className="space-y-1">
                    {meeting.summary.action_items.map((item: any, i: number) => (
                      <li key={i} className="flex gap-2"><span className="text-blue-600">☐</span><span>{item.text}</span></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="text-center text-gray-500">
              {meeting.status === "processing" ? "Summary being generated..." : "No summary available"}
            </p>
          )}
        </div>
      )}

      {activeTab === "notes" && (
        <div className="space-y-4">
          {/* Add Note Form */}
          <div className="bg-white border rounded-lg p-4">
            <h3 className="font-medium text-gray-900 mb-3">Add Note @ {formatTime(currentTime)}</h3>
            <textarea
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              placeholder="Type your note here..."
              className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              rows={3}
            />
            <div className="flex justify-between items-center mt-3">
              <select
                value={noteType}
                onChange={(e) => setNoteType(e.target.value)}
                className="px-3 py-2 border rounded-md text-sm"
              >
                {NOTE_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
              <button
                onClick={addNote}
                disabled={addingNote || !noteContent.trim()}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {addingNote ? "Adding..." : "Add Note"}
              </button>
            </div>
          </div>

          {/* Notes List */}
          {meeting.notes?.length === 0 ? (
            <div className="bg-white border rounded-lg p-8 text-center text-gray-500">
              No notes yet. Add one above!
            </div>
          ) : (
            meeting.notes?.map((note: any) => (
              <div key={note.id} className="bg-white border rounded-lg p-4">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${getNoteTypeColor(note.note_type)}`}>
                      {getNoteTypeLabel(note.note_type)}
                    </span>
                    <span className="text-xs text-gray-400">
                      @{formatTime(note.recording_offset)} • {new Date(note.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => { if (audioRef.current) { audioRef.current.currentTime = note.recording_offset; audioRef.current.play(); setIsPlaying(true); }}}
                      className="text-blue-600 hover:text-blue-800 text-xs"
                    >
                      Jump
                    </button>
                    <button
                      onClick={() => deleteNote(note.id)}
                      className="text-red-600 hover:text-red-800 text-xs"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <p className="text-gray-700">{note.content}</p>
              </div>
            ))
          )}
        </div>
      )}
    </main>
  );
}
