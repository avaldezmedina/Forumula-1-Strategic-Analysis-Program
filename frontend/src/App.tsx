import { BrowserRouter, Route, Routes } from "react-router-dom";
import { SessionPicker } from "./components/SessionPicker";
import { ReplayViewer } from "./pages/ReplayViewer";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SessionPicker />} />
        <Route path="/replay/:sessionKey" element={<ReplayViewer />} />
      </Routes>
    </BrowserRouter>
  );
}
