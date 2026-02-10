"use client";

import { useEffect, useState } from "react";

interface Meeting {
  id: string;
  title: string;
  status: string;
  created_at: string;
}

export default function Home() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMeetings();
  }, []);

  const fetchMeetings = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/v1/meetings");
      if (!response.ok) {
        throw new Error("Failed to fetch meetings");
      }
      const data = await response.json();
      setMeetings(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const createMeeting = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/v1/meetings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ title: "New Meeting" }),
      });
      if (!response.ok) {
        throw new Error("Failed to create meeting");
      }
      fetchMeetings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    }
  };

  return (
    <div className="min-h-screen p-8">
      <main className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold mb-8">MeetScribe</h1>
        <p className="text-gray-600 mb-8">Local-First Linux Meeting Assistant</p>

        <div className="mb-8">
          <button
            onClick={createMeeting}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Create Meeting
          </button>
        </div>

        {loading && <p>Loading meetings...</p>}
        
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <h2 className="text-2xl font-semibold">Meetings ({meetings.length})</h2>
          
          {meetings.length === 0 && !loading && (
            <p className="text-gray-500">No meetings yet. Create one to get started!</p>
          )}

          {meetings.map((meeting) => (
            <div
              key={meeting.id}
              className="border rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              <h3 className="text-xl font-medium">{meeting.title}</h3>
              <div className="flex gap-4 mt-2 text-sm text-gray-600">
                <span className={`px-2 py-1 rounded ${
                  meeting.status === "idle" ? "bg-gray-200" :
                  meeting.status === "recording" ? "bg-red-200" :
                  meeting.status === "completed" ? "bg-green-200" :
                  "bg-yellow-200"
                }`}>
                  {meeting.status}
                </span>
                <span>{new Date(meeting.created_at).toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
