import { Navigate, Route, Routes } from "react-router-dom";

import AppShell from "./components/layout/AppShell";
import DailyPage from "./pages/DailyPage";
import DocumentsPage from "./pages/DocumentsPage";
import QueryPage from "./pages/QueryPage";
import SearchPage from "./pages/SearchPage";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/daily" element={<DailyPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/query" element={<QueryPage />} />
        <Route path="/documents" element={<DocumentsPage />} />

        <Route
          path="*"
          element={<Navigate to="/daily" replace />}
        />
      </Route>
    </Routes>
  );
}

export default App;