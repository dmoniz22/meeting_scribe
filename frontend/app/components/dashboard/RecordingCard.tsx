"use client";

import { Mic, MicOff, Play } from "lucide-react";
import Button from "../ui/Button";
import Card from "../ui/Card";
import { formatDuration } from "@/app/lib/format";
import type { RecordingStatus } from "@/app/lib/constants";

interface RecordingCardProps {
  status: RecordingStatus | null;
  onStart: () => void;
  onStop: () => void;
  loading: boolean;
}

export default function RecordingCard({ status, onStart, onStop, loading }: RecordingCardProps) {
  if (status?.is_recording) {
    return (
      <Card className="overflow-hidden">
        <div className="bg-gradient-to-r from-rose-500 to-red-600 p-6 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                <span className="absolute inline-flex h-4 w-4 rounded-full bg-white opacity-75 animate-ping"></span>
                <span className="relative inline-flex rounded-full h-4 w-4 bg-white"></span>
              </div>
              <div>
                <p className="text-rose-100 text-sm font-medium">Recording in Progress</p>
                <p className="text-4xl font-bold font-mono">{formatDuration(status.duration_seconds || 0)}</p>
              </div>
            </div>
            <Button
              variant="secondary"
              size="lg"
              onClick={onStop}
              isLoading={loading}
              leftIcon={<MicOff className="w-5 h-5" />}
              className="shadow-lg"
            >
              {loading ? "Stopping..." : "Stop Recording"}
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-8 text-center">
      <div className="w-16 h-16 bg-gradient-to-br from-rose-500 to-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-rose-500/20">
        <Mic className="w-8 h-8 text-white" />
      </div>
      <h3 className="text-xl font-semibold text-slate-900 mb-2">Ready to Record</h3>
      <p className="text-slate-500 mb-6 max-w-md mx-auto">
        Click below to start recording your meeting. You&apos;ll be able to take notes in real-time while the recording is active.
      </p>
      <Button
        variant="danger"
        size="lg"
        onClick={onStart}
        isLoading={loading}
        leftIcon={<Play className="w-5 h-5" />}
        className="hover:shadow-xl hover:shadow-rose-500/25 hover:scale-105 transition-all"
      >
        {loading ? "Starting..." : "Start Recording"}
      </Button>
      {!status && (
        <p className="text-xs text-amber-600 mt-4">
          Note: Make sure the backend API is running on port 8003
        </p>
      )}
    </Card>
  );
}
