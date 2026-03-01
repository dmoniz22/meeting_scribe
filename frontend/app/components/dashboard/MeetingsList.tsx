"use client";

import { useState } from "react";
import { Search, Filter, CalendarDays } from "lucide-react";
import MeetingCard from "./MeetingCard";
import type { Meeting } from "@/app/lib/constants";

interface MeetingsListProps {
  meetings: Meeting[];
  loading: boolean;
  onDelete: (id: string) => void;
}

export default function MeetingsList({ meetings, loading, onDelete }: MeetingsListProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filteredMeetings = meetings
    .filter((m) => statusFilter === "all" || m.status === statusFilter)
    .filter((m) => !searchQuery || m.title.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="mt-8">
      <div className="mb-6 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Recent Meetings</h2>
          <p className="text-sm text-slate-500">{filteredMeetings.length} meetings</p>
        </div>
        <div className="flex gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent w-48"
            />
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="pl-10 pr-8 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 bg-white"
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
        <div className="text-center py-16 bg-white rounded-2xl border border-slate-200">
          <CalendarDays className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500">No meetings found</p>
          <p className="text-sm text-slate-400 mt-1">Start your first recording above</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {filteredMeetings.map((meeting) => (
            <MeetingCard
              key={meeting.id}
              meeting={meeting}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
