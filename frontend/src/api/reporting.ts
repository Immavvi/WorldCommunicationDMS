import {apiRequest} from "./client";
export type Dashboard={operational:Record<string,string|number>;financial?:Record<string,string|number>};
export const getDashboard=(token:string)=>apiRequest<Dashboard>("/dashboard",{token});
export const getReport=(token:string,name:string,query="")=>apiRequest<Record<string,unknown>[]>(`/reports/${name}${query?`?${query}`:""}`,{token});
export async function exportReport(token:string,name:string,query=""){const response=await fetch(`/api/v1/reports/${name}/export.xlsx${query?`?${query}`:""}`,{headers:{Authorization:`Bearer ${token}`}});if(!response.ok)throw new Error("Unable to export report.");const url=URL.createObjectURL(await response.blob());const anchor=document.createElement("a");anchor.href=url;anchor.download=`wcdms-${name}.xlsx`;anchor.click();URL.revokeObjectURL(url);}
