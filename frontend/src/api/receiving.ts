import { apiRequest } from "./client";

export type ReceiptLine={id:string;purchase_order_line_id:string;ordered_quantity_snapshot:string;previously_accepted_snapshot:string;quantity_received:string;quantity_accepted:string;quantity_short:string;quantity_damaged:string;quantity_rejected:string;quantity_excess:string;description_snapshot:string;unit_snapshot:string;remarks?:string};
export type MaterialReceipt={id:string;receipt_number:string;purchase_order_id:string;po_number_snapshot:string;vendor_snapshot:Record<string,string>;receipt_date:string;receiving_location:string;status:string;lines:ReceiptLine[]};
export type ReceiptPosition={purchase_order_line_id:string;line_number:number;description:string;unit:string;ordered_quantity:string;accepted_to_date:string;pending_quantity:string};
export const listReceipts=(token:string)=>apiRequest<MaterialReceipt[]>("/material-receipts",{token});
export const createReceipt=(token:string,data:Record<string,unknown>)=>apiRequest<MaterialReceipt>("/material-receipts",{method:"POST",token,body:JSON.stringify(data)});
export const getReceipt=(token:string,id:string)=>apiRequest<MaterialReceipt>(`/material-receipts/${id}`,{token});
export const transitionReceipt=(token:string,id:string,action:string,reason:string)=>apiRequest<MaterialReceipt>(`/material-receipts/${id}/actions`,{method:"POST",token,body:JSON.stringify({action,reason})});
export const updateReceiptLine=(token:string,receiptId:string,lineId:string,data:Record<string,unknown>)=>apiRequest<MaterialReceipt>(`/material-receipts/${receiptId}/lines/${lineId}`,{method:"PUT",token,body:JSON.stringify(data)});
export const getReceiptPosition=(token:string,poId:string)=>apiRequest<ReceiptPosition[]>(`/purchase-orders/${poId}/receipt-position`,{token});
