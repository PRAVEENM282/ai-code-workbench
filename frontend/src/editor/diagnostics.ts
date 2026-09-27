import { MarkerSeverity, type editor } from 'monaco-editor';
import type { Finding } from '../api/types';

export function toMonacoMarkers(findings: Finding[]): editor.IMarkerData[] {
  return findings
    .filter((finding) => finding.line_number > 0)
    .map((finding) => ({
      startLineNumber: finding.line_number,
      endLineNumber: finding.line_number,
      startColumn: Math.max(finding.column ?? 1, 1),
      endColumn: Math.max((finding.column ?? 1) + 1, 2),
      severity:
        finding.severity === 'error'
          ? MarkerSeverity.Error
          : finding.severity === 'info'
            ? MarkerSeverity.Info
            : MarkerSeverity.Warning,
      message: finding.tool
        ? `${finding.tool}: ${finding.message ?? finding.description ?? ''}`
        : finding.message ?? finding.description ?? '',
      code: finding.rule,
      source: finding.tool ?? 'workbench',
    }));
}
