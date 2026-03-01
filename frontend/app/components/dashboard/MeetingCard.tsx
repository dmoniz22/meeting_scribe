"use client";

import Link from "next/link";
import { Mic, Trash2, FileText, CheckCircle2 } from "lucide-react";
import Badge from "../ui/Badge";
import { Clock, Calendar } from "lucide-react";
import type { Meeting } from "@/app/lib/constants";
import { STATUS_CONFIG, NOTE_TYPES } from "@/app/lib/constants";
import { formatDuration, formatDate } from "@/app/lib/format";

interface MeetingCardProps {
  meeting: Meeting;
  onDelete: (id: string) => void;
}

export default function MeetingCard({ meeting, onDelete }: MeetingCardProps) {
  const statusConfig = STATUS_CONFIG[meeting.status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.idle;
  
  const getStatusIcon = () => {
    switch (meeting.status) {
      case "recording":
        return <Mic className="w-5 h-5 text-rose-600" />;
      case "completed":
        return <CheckCircle2 className="w-5 h-5 text-emerald-600" />;
      default:
        return <FileText className="w-5 h-5 text-slate-600" />;
    }
  };

  const getStatusBg = () => {
    switch (meeting.status) {
      case "recording":
        return "bg-rose-100";
      case "processing":
        return "bg-amber-100";
      case "completed":
        return "bg-emerald-100";
      default:
        return "bg-slate-100";
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md transition-all group">
      <div className="flex items-center justify-between">
        <Link href={`/meetings/${meeting.id}`} className="flex-1">
          <div className="flex items-center gap-4">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${getStatusBg()}`}>
              {getStatusIcon()}
            </div>
            <div>
              <h3 className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">
                {meeting.title}
              </h3>
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <span className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" />
                  {formatDuration(meeting.duration_seconds)}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5" />
                  {formatDate(meeting.created_at)}
                </span>
              </div>
            </div>
          </div>
        </Link>
        <div className="flex items-center gap-3">
          <Badge color={statusConfig.color}>
            {statusConfig.label}
          </Badge>
          <button
            onClick={() => onDelete(meeting.id)}
            className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
            title="Delete meeting"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
