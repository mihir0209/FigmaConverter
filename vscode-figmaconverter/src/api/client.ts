import * as vscode from "vscode";
import { ConversionRequest, ConversionResponse, JobStatus, ImportResult } from "./types";

export class ApiClient {
  private baseUrl: string;

  constructor() {
    const config = vscode.workspace.getConfiguration("figmaconverter");
    this.baseUrl = config.get<string>("serverUrl") || "http://localhost:8000";
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const resp = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    if (!resp.ok) {
      const body = await resp.text();
      throw new Error(`API error ${resp.status}: ${body}`);
    }
    return resp.json() as Promise<T>;
  }

  async startConversion(req: ConversionRequest): Promise<ConversionResponse> {
    return this.request<ConversionResponse>("/api/convert", {
      method: "POST",
      body: JSON.stringify(req),
    });
  }

  async pollStatus(jobId: string, onProgress?: (pct: number, msg: string) => void): Promise<JobStatus> {
    while (true) {
      const status = await this.request<JobStatus>(`/api/status/${jobId}`);
      if (onProgress && status.progress !== undefined) {
        onProgress(status.progress, status.message);
      }
      if (status.status === "completed" || status.status === "failed") {
        return status;
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  async downloadFiles(jobId: string, fileList: string[]): Promise<ImportResult> {
    return this.request<ImportResult>(`/api/download-files/${jobId}`, {
      method: "POST",
      body: JSON.stringify({ files: fileList }),
    });
  }
}
