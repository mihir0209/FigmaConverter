import * as vscode from "vscode";
import * as path from "path";

export async function writeFiles(
  rootUri: vscode.Uri,
  files: Record<string, string>,
  onProgress?: (file: string) => void
): Promise<number> {
  let count = 0;
  for (const [relPath, content] of Object.entries(files)) {
    const fullPath = path.join(rootUri.fsPath, relPath);
    const dir = path.dirname(fullPath);

    await vscode.workspace.fs.createDirectory(vscode.Uri.file(dir));

    // Check for existing file
    const uri = vscode.Uri.file(fullPath);
    try {
      await vscode.workspace.fs.stat(uri);
      // File exists — ask user
      const overwrite = await vscode.window.showQuickPick(
        ["Yes", "Yes to All", "Skip"],
        { placeHolder: `Overwrite ${relPath}?` }
      );
      if (overwrite === "Skip" || overwrite === undefined) {
        continue;
      }
    } catch {
      // File doesn't exist — safe to write
    }

    await vscode.workspace.fs.writeFile(uri, Buffer.from(content, "utf-8"));
    count++;
    if (onProgress) onProgress(relPath);
  }
  return count;
}
