import { useState } from "react";
import { Toaster } from "sonner";
import UploadScreen from "./screens/UploadScreen";
import Editor from "./screens/Editor";

export default function App() {
  const [projectId, setProjectId] = useState(null);

  return (
    <div className="h-screen w-full bg-background text-white overflow-hidden">
      <Toaster theme="dark" position="top-center" richColors />
      {projectId ? (
        <Editor projectId={projectId} onReset={() => setProjectId(null)} />
      ) : (
        <UploadScreen onReady={setProjectId} />
      )}
    </div>
  );
}
