export function renderLoadingState(): string {
  return `
    <main class="loading-state" aria-live="polite">
      <div class="brand-mark">A</div>
      <p class="eyebrow">Alcove Console</p>
      <h1>Loading local snapshot</h1>
      <p>Reading your local Alcove index. Large knowledge bases can take a moment.</p>
    </main>
  `;
}
