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
import { TaxInvoicesPage } from "./pages/TaxInvoicesPage";
import { TaxInvoiceDetailPage } from "./pages/TaxInvoiceDetailPage";
import { ProformaInvoicesPage } from "./pages/ProformaInvoicesPage";
import { ProformaInvoiceDetailPage } from "./pages/ProformaInvoiceDetailPage";
import { DispatchPage } from "./pages/DispatchPage";
import { ChallanDetailPage } from "./pages/ChallanDetailPage";
import { QuotationsPage } from "./pages/QuotationsPage";
import { QuotationDetailPage } from "./pages/QuotationDetailPage";
import { AssetsPage } from "./pages/AssetsPage";
import { PaymentsPage } from "./pages/PaymentsPage";
import { ReceivablesPage } from "./pages/ReceivablesPage";

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
              <Route path="/assets" element={<AssetsPage />} />
              <Route path="/payments" element={<PaymentsPage />} />
              <Route path="/receivables" element={<ReceivablesPage />} />
              <Route path="/material-receipts/:receiptId" element={<ReceiptDetailPage />} />
              <Route path="/dispatch" element={<DispatchPage />} />
              <Route path="/supply-challans/:challanId" element={<ChallanDetailPage />} />
              <Route path="/proforma-invoices" element={<ProformaInvoicesPage />} />
              <Route path="/proforma-invoices/:piId" element={<ProformaInvoiceDetailPage />} />
              <Route path="/tax-invoices" element={<TaxInvoicesPage />} />
              <Route path="/tax-invoices/:invoiceId" element={<TaxInvoiceDetailPage />} />
              <Route path="/quotations" element={<QuotationsPage />} />
              <Route path="/quotations/:quotationId" element={<QuotationDetailPage />} />
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
