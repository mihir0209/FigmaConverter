import * as vscode from "vscode";

export async function configureServer() {
  const url = await vscode.window.showInputBox({
    prompt: "Enter the FigmaConverter API server URL",
    value: vscode.workspace.getConfiguration("figmaconverter").get<string>("serverUrl"),
    placeHolder: "http://localhost:8000",
  });
  if (!url) return;

  await vscode.workspace.getConfiguration("figmaconverter").update("serverUrl", url, true);
  vscode.window.showInformationMessage(`FigmaConverter: Server URL set to ${url}`);
}
