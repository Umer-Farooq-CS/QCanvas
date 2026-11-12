/**
 * Shown the instant someone navigates to the editor (e.g. "Open editor" in
 * the site navbar). Without it the click had no visible effect for 1.5-3.5 s
 * while the editor bundle loaded, which read as a broken button. Matches the
 * editor's own loading screen so the hand-off is seamless.
 */
export default function EditorLoading() {
  return (
    <div className="flex h-screen items-center justify-center bg-editor-bg" role="status" aria-live="polite">
      <div className="flex flex-col items-center space-y-4">
        <div className="spinner h-8 w-8 rounded-full border-4 border-quantum-blue-light border-t-transparent" />
        <p className="text-editor-text">Loading QCanvas...</p>
      </div>
    </div>
  );
}
