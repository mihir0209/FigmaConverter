export interface ConversionRequest {
  figma_url: string;
  target_framework: string;
  pat_token?: string;
  include_components?: boolean;
  style_engine?: string;
  component_library?: string;
}

export interface ConversionResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  message: string;
  result?: {
    framework: string;
    files_generated: number;
    components_collected: number;
    zip_path: string;
    file_list: string[];
  };
}

export interface CodebaseContext {
  framework: string | null;
  dependencies: Record<string, string>;
  existing_components: string[];
  styling_approach: string | null;
}

export interface ImportResult {
  files: Record<string, string>;
  file_list: string[];
  framework: string;
}
