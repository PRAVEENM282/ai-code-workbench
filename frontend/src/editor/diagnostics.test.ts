import { describe, expect, it } from 'vitest';
import { MarkerSeverity } from 'monaco-editor';
import { toMonacoMarkers } from './diagnostics';

describe('toMonacoMarkers', () => {
  it('maps normalized findings to editor lines and hover messages', () => {
    const [marker] = toMonacoMarkers([
      { line_number: 7, column: 3, severity: 'error', message: 'Undefined name', rule: 'E0602', tool: 'Pylint' },
      { line_number: 0, message: 'No source location' },
    ]);

    expect(marker).toMatchObject({
      startLineNumber: 7,
      startColumn: 3,
      severity: MarkerSeverity.Error,
      message: 'Pylint: Undefined name',
      code: 'E0602',
    });
  });

  it('uses AI review descriptions for inline markers', () => {
    const [marker] = toMonacoMarkers([
      { line_number: 2, issue_type: 'bug', description: 'Potential race', suggested_fix: 'Lock state' },
    ]);
    expect(marker.message).toBe('Potential race');
  });
});
