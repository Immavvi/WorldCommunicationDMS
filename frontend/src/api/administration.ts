import {apiRequest} from "./client";
export type Numbering={id:string;document_type:string;prefix:string;next_number:number;padding:number;preview:string};
export type SystemStatus={status:string;application:string;version:string;environment:string;database:string;schema_revision:string};
export const getNumbering=(token:string)=>apiRequest<Numbering[]>("/admin/numbering",{token});
export const getSystemStatus=(token:string)=>apiRequest<SystemStatus>("/admin/system-status",{token});
