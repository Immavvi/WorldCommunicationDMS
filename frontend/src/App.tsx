import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppLayout } from "./layouts/AppLayout";
import { ForbiddenPage } from "./pages/ForbiddenPage";
import { LoginPage } from "./pages/LoginPage";
import { MasterDataPage } from "./pages/MasterDataPage";
import { LoaDetailPage } from "./pages/LoaDetailPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ProcurementPage } from "./pages/ProcurementPage";
import { PurchaseOrderDetailPage } from "./pages/PurchaseOrderDetailPage";
import { RequirementDetailPage } from "./pages/RequirementDetailPage";
import { ReceivingPage } from "./pages/ReceivingPage";
import { ReceiptDetailPage } from "./pages/ReceiptDetailPage";
import { StatusPage } from "./pages/StatusPage";
import { UsersPage } from "./pages/UsersPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppLayout>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/forbidden" element={<ForbiddenPage />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<StatusPage />} />
              <Route path="/master-data" element={<MasterDataPage />} />
              <Route path="/projects" element={<ProjectsPage />} />
              <Route path="/loas/:loaId" element={<LoaDetailPage />} />
              <Route path="/procurement" element={<ProcurementPage />} />
              <Route path="/purchase-orders/:poId" element={<PurchaseOrderDetailPage />} />
              <Route path="/procurement-requirements/:requirementId" element={<RequirementDetailPage />} />
              <Route path="/receiving" element={<ReceivingPage />} />
              <Route path="/material-receipts/:receiptId" element={<ReceiptDetailPage />} />
            </Route>
            <Route element={<ProtectedRoute requiredRole="SUPER-ADMIN" />}>
              <Route path="/users" element={<UsersPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppLayout>
      </AuthProvider>
    </BrowserRouter>
  );
}
