import { Routes, Route, Navigate } from "react-router-dom";
import Chatbot from "./pages/Chatbot";
import Summaries from "./pages/Summaries";
import AssistedReader from "./pages/AssistedReader";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Chatbot />} />
      <Route path="/summaries" element={<Summaries />} />
      <Route path="/viewer" element={<AssistedReader />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
