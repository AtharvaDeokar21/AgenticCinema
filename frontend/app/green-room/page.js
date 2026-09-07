import CurtainCall from "@/components/CurtainCall";
import Proscenium from "@/components/Proscenium";
import ChatRoom from "@/components/chat/ChatRoom";
import "./green-room.css";

export const metadata = {
  title: "The Green Room — Agentic Cinema",
  description:
    "Talk to the crew. Bring footage, a voice note, a still or a brief, and the job goes to whichever agent it belongs to.",
};

export default function GreenRoomPage() {
  return (
    <>
      {/* the same curtain reveal as the front page */}
      <CurtainCall />
      {/* the same velvet frame, vignette and grain */}
      <Proscenium />
      <ChatRoom />
    </>
  );
}
