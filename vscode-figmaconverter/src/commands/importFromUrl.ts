import * as vscode from "vscode";
import { ApiClient } from "../api/client";
import { scanWorkspace } from "../utils/workspaceScanner";
import { writeFiles } from "../utils/fileWriter";

export async function importFromUrl(api: ApiClient, context: vscode.ExtensionContext) {
  const workspaceRoot = vscode.workspace.workspaceFolders?.[0];
  if (!workspaceRoot) {
    vscode.window.showErrorMessage("FigmaConverter: Open a workspace first");
    return;
  }

  const figmaUrl = await vscode.window.showInputBox({
    prompt: "Paste the Figma file URL",
    placeHolder: "https://www.figma.com/file/...",
    validateInput: (val) => (val.includes("figma.com") ? null : "Not a valid Figma URL"),
  });
  if (!figmaUrl) return;

  const framework = await vscode.window.showQuickPick(
    ["react", "vue", "angular", "html", "nextjs", "react_ts", "flutter"],
    { placeHolder: "Select target framework (or let us auto-detect)" }
  );
  if (!framework) return;

  const config = vscode.workspace.getConfiguration("figmaconverter");
  const patToken = config.get<string>("apiToken") || undefined;

  // Scan workspace for codebase context
  const contextInfo = scanWorkspace(workspaceRoot.uri);
  const detectedFramework = contextInfo.framework || framework;

  vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: `FigmaConverter: Generating ${detectedFramework} code...`,
      cancellable: true,
    },
    async (progress, token) => {
      const resp = await api.startConversion({
        figma_url: figmaUrl,
        target_framework: detectedFramework,
        pat_token: patToken,
        style_engine: contextInfo.styling_approach || undefined,
      });

      token.onCancellationRequested(() => {
        vscode.window.showWarningMessage("FigmaConverter: Conversion cancelled");
      });

      const status = await api.pollStatus(resp.job_id, (pct, msg) => {
        progress.report({ message: msg, increment: pct });
      });

      if (status.status === "failed") {
        vscode.window.showErrorMessage(`FigmaConverter: Conversion failed — ${status.message}`);
        return;
      }

      const result = await api.downloadFiles(resp.job_id, status.result?.file_list || []);

      const count = await writeFiles(workspaceRoot.uri, result.files, (file) => {
        progress.report({ message: `Writing ${file}` });
      });

      vscode.window.showInformationMessage(
        `FigmaConverter: Imported ${count} file(s) from Figma`
      );
    }
  );
}
