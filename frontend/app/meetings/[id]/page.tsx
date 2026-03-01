"use client";

import { useParams } from "next/navigation";
import MeetingDetail from "../../components/meeting/MeetingDetail";

export default function MeetingPage() {
  const params = useParams();
  const meetingId = params.id as string;

  if (!meetingId) {
    return <div className="text-center py-12">Meeting not found</div>;
  }

  return <MeetingDetail meetingId={meetingId} />;
}
