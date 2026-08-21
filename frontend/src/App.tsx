import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppLayout } from "./layouts/AppLayout";
import { StatusPage } from "./pages/StatusPage";

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="*" element={<StatusPage />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}
