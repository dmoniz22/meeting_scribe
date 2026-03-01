"use client";

import { useState } from "react";
import { Plus, FileText, CheckCircle2 } from "lucide-react";
import Card from "../ui/Card";
import Button from "../ui/Button";
import { NOTE_TYPES, type RecordingStatus, type Note } from "@/app/lib/constants";
import { formatDuration } from "@/app/lib/format";

interface LiveNotesProps {
  recordingStatus: RecordingStatus;
  notes: Note[];
  onAddNote: (content: string, noteType: string) => Promise<void>;
}

export default function LiveNotes({ recordingStatus, notes, onAddNote }: LiveNotesProps) {
  const [content, setContent] = useState("");
  const [noteType, setNoteType] = useState("general");
  const [adding, setAdding] = useState(false);

  const handleSubmit = async () => {
    if (!content.trim()) return;
    setAdding(true);
    await onAddNote(content, noteType);
    setContent("");
    setAdding(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && e.ctrlKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const getNoteTypeConfig = (type: string) => NOTE_TYPES.find(t => t.id === type) || NOTE_TYPES[0];

  return (
    <Card className="mt-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
          <FileText className="w-5 h-5 text-slate-400" />
          Live Notes ({notes.length})
        </h3>
        <span className="text-sm text-slate-500">Take notes while recording</span>
      </div>

      <div className="flex gap-4 mb-4">
        <div className="flex-1">
          <textarea
            placeholder="Type your note here... Press Ctrl+Enter to save"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={4}
            className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none text-base leading-relaxed"
          />
          <p className="text-xs text-slate-400 mt-2">Ctrl+Enter to save • {content.length} characters</p>
        </div>
        <div className="flex flex-col gap-2 w-40">
          <select
            value={noteType}
            onChange={(e) => setNoteType(e.target.value)}
            className="px-4 py-3 border border-slate-200 rounded-xl text-sm bg-white"
          >
            {NOTE_TYPES.map(t => (
              <option key={t.id} value={t.id}>{t.label}</option>
            ))}
          </select>
          <Button
            onClick={handleSubmit}
            disabled={adding || !content.trim()}
            isLoading={adding}
            leftIcon={<Plus className="w-4 h-4" />}
          >
            Add Note
          </Button>
        </div>
      </div>

      {/* Notes List */}
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {notes.length === 0 ? (
          <div className="text-center py-8 bg-slate-50 rounded-xl">
            <FileText className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-slate-500 text-sm">No notes yet. Start typing above!</p>
          </div>
        ) : (
          notes.map((note) => {
            const typeConfig = getNoteTypeConfig(note.note_type);
            return (
              <div key={note.id} className="flex items-start gap-3 p-4 bg-slate-50 rounded-xl">
                <span className={`text-xs px-3 py-1.5 rounded-lg font-medium flex items-center gap-1.5 ${typeConfig.color}`}>
                  <CheckCircle2 className="w-3 h-3" />
                  {typeConfig.label}
                </span>
                <span className="text-xs text-slate-400 font-mono mt-1.5">
                  {formatDuration(note.recording_offset)}
                </span>
                <p className="text-slate-700 flex-1 text-sm">{note.content}</p>
              </div>
            );
          })
        )}
      </div>
    </Card>
  );
}
