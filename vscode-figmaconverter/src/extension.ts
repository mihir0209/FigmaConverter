import * as vscode from "vscode";
import { ApiClient } from "./api/client";
import { importFromUrl } from "./commands/importFromUrl";
import { configureServer } from "./commands/configureServer";

let api: ApiClient | undefined;

export function activate(context: vscode.ExtensionContext) {
  api = new ApiClient();

  context.subscriptions.push(
    vscode.commands.registerCommand("figmaconverter.importFromUrl", () => {
      importFromUrl(api!, context);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("figmaconverter.configureServer", configureServer)
  );

  vscode.window.showInformationMessage("FigmaConverter extension is active");
}

export function deactivate() {
  api = undefined;
}
